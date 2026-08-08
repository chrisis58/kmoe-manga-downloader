package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
)

// Native Messaging protocol: 4-byte uint32 length prefix (native byte order), then JSON.

type Request struct {
	Action string      `json:"action"`
	Params Params      `json:"params"`
	Target interface{} `json:"target"` // "local" or {"host":"...","user":"...","port":22}
}

type Params struct {
	BookURL  string `json:"book_url,omitempty"`
	VolIDs   string `json:"vol_ids,omitempty"`
	Format   string `json:"format,omitempty"`
	Dest     string `json:"dest,omitempty"`
	VolType  string `json:"vol_type,omitempty"`
	TaskID   string `json:"task_id,omitempty"`
	Wait     int    `json:"wait,omitempty"`
}

type SSHConfig struct {
	Host string `json:"host"`
	User string `json:"user"`
	Port int    `json:"port"`
}

type Response struct {
	Code   int         `json:"code"`
	Msg    string      `json:"msg"`
	Action string      `json:"action"`
	Data   interface{} `json:"data"`
}

func main() {
	reader := bufio.NewReader(os.Stdin)
	writer := bufio.NewWriter(os.Stdout)

	for {
		req, err := readMessage(reader)
		if err == io.EOF {
			break
		}
		if err != nil {
			sendMessage(writer, Response{Code: 200, Msg: fmt.Sprintf("read error: %v", err)})
			break
		}

		resp := handleRequest(req)
		sendMessage(writer, resp)
	}
}

func readMessage(r io.Reader) (*Request, error) {
	var length uint32
	if err := binary.Read(r, binary.LittleEndian, &length); err != nil {
		return nil, err
	}
	data := make([]byte, length)
	if _, err := io.ReadFull(r, data); err != nil {
		return nil, err
	}
	var req Request
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("json decode: %w", err)
	}
	return &req, nil
}

func sendMessage(w *bufio.Writer, resp Response) {
	data, _ := json.Marshal(resp)
	binary.Write(w, binary.LittleEndian, uint32(len(data)))
	w.Write(data)
	w.Flush()
}

func handleRequest(req *Request) Response {
	cmd, err := buildCommand(req)
	if err != nil {
		return Response{Code: 103, Msg: err.Error(), Action: req.Action}
	}

	switch target := req.Target.(type) {
	case string:
		if target == "local" {
			return runLocal(req.Action, cmd)
		}
		return Response{Code: 104, Msg: "invalid target: " + target, Action: req.Action}

	case map[string]interface{}:
		host, _ := target["host"].(string)
		if host != "" {
			user, _ := target["user"].(string)
			port, ok := target["port"].(float64)
			if !ok {
				port = 22
			}
			return runSSH(req.Action, cmd, SSHConfig{
				Host: host,
				User: user,
				Port: int(port),
			})
		}
		return Response{Code: 104, Msg: "ssh target missing host", Action: req.Action}

	default:
		return Response{Code: 104, Msg: "invalid target config", Action: req.Action}
	}
}

func buildCommand(req *Request) ([]string, error) {
	cmd := []string{"kmdr", "--mode", "toolcall"}

	switch req.Action {
	case "download":
		cmd = append(cmd, "download",
			"-l", req.Params.BookURL,
			"--vol-ids", req.Params.VolIDs,
			"--background",
		)
		if req.Params.Format != "" {
			cmd = append(cmd, "-f", req.Params.Format)
		}
		if req.Params.Dest != "" {
			cmd = append(cmd, "-d", req.Params.Dest)
		}
		if req.Params.VolType != "" {
			cmd = append(cmd, "-t", req.Params.VolType)
		}

	case "status":
		cmd = append(cmd, "status")

	case "progress":
		cmd = append(cmd, "progress", req.Params.TaskID)
		wait := req.Params.Wait
		if wait > 0 {
			cmd = append(cmd, "--wait", fmt.Sprintf("%d", wait))
		} else {
			cmd = append(cmd, "--wait", "0")
		}

	default:
		return nil, fmt.Errorf("unknown action: %s", req.Action)
	}

	return cmd, nil
}

func runLocal(action string, cmd []string) Response {
	var stderr bytes.Buffer
	c := exec.Command(cmd[0], cmd[1:]...)
	c.Stderr = &stderr
	stdout, err := c.Output()
	if err != nil {
		errMsg := strings.TrimSpace(stderr.String())
		if errMsg == "" {
			errMsg = err.Error()
		}
		if exitErr, ok := err.(*exec.ExitError); ok {
			return Response{
				Code:   exitErr.ExitCode(),
				Msg:    errMsg,
				Action: action,
			}
		}
		if _, ok := err.(*exec.Error); ok {
			return Response{
				Code:   101,
				Msg:    "kmdr 未找到，请确认已安装 kmoe-manga-downloader",
				Action: action,
			}
		}
		return Response{Code: 500, Msg: err.Error(), Action: action}
	}

	resp := parseKmdrOutput(action, string(stdout))
	resp.Data = attachCommand(resp.Data, cmd)
	return resp
}

func runSSH(action string, kmdrCmd []string, ssh SSHConfig) Response {
	if ssh.Host == "" {
		return Response{Code: 102, Msg: "SSH 目标主机未配置", Action: action}
	}

	target := ssh.Host
	if ssh.User != "" {
		target = ssh.User + "@" + ssh.Host
	}

	quoted := strings.Join(kmdrCmd, " ")
	sshCmd := exec.Command("ssh",
		"-p", fmt.Sprintf("%d", ssh.Port),
		"-o", "ConnectTimeout=10",
		"-o", "BatchMode=yes",
		target,
		quoted,
	)

	var stderr bytes.Buffer
	sshCmd.Stderr = &stderr
	stdout, err := sshCmd.Output()
	if err != nil {
		errMsg := strings.TrimSpace(stderr.String())
		if errMsg == "" {
			errMsg = err.Error()
		}
		hint := ""
		switch {
		case strings.Contains(errMsg, "Permission denied"):
			hint = " (请确认 SSH key 已配置)"
		case strings.Contains(errMsg, "Could not resolve") || strings.Contains(errMsg, "Name or service not known"):
			hint = " (无法解析主机名)"
		case strings.Contains(errMsg, "Connection refused"):
			hint = " (连接被拒绝，请检查目标主机和端口)"
		case strings.Contains(errMsg, "Connection timed out"):
			hint = " (连接超时)"
		}
		return Response{
			Code:   102,
			Msg:    fmt.Sprintf("SSH 连接失败: %s%s", errMsg, hint),
			Action: action,
		}
	}

	resp := parseKmdrOutput(action, string(stdout))
	resp.Data = attachCommand(resp.Data, kmdrCmd)
	return resp
}

// attachCommand always attaches the executed command to response data for diagnostics.
func attachCommand(data interface{}, cmd []string) interface{} {
	if m, ok := data.(map[string]interface{}); ok {
		m["_cmd"] = strings.Join(cmd, " ")
		return m
	}
	return data
}

// parseKmdrOutput finds the last {"type":"result",...} line in kmdr's NDJSON output.
func parseKmdrOutput(action, stdout string) Response {
	lines := strings.Split(strings.TrimSpace(stdout), "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if !strings.HasPrefix(line, "{") {
			continue
		}
		var parsed map[string]interface{}
		if err := json.Unmarshal([]byte(line), &parsed); err != nil {
			continue
		}
		if t, ok := parsed["type"].(string); ok && t == "result" {
			code := 0
			if c, ok := parsed["code"].(float64); ok {
				code = int(c)
			}
			msg := "success"
			if m, ok := parsed["msg"].(string); ok {
				msg = m
			}
			return Response{
				Code:   code,
				Msg:    msg,
				Action: action,
				Data:   parsed["data"],
			}
		}
	}

	// Fallback: return raw output
	if stdout != "" {
		return Response{
			Code:   0,
			Msg:    "success",
			Action: action,
			Data:   map[string]string{"raw": stdout},
		}
	}
	return Response{
		Code:   0,
		Msg:    "success",
		Action: action,
		Data:   nil,
	}
}
