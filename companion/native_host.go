package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

// ── Native Messaging protocol ────────────────────────────────────

// readMessage reads a length-prefixed JSON message from stdin.
func readMessage(r io.Reader) (*Request, error) {
	var length uint32
	if err := binary.Read(r, binary.LittleEndian, &length); err != nil {
		return nil, err
	}
	data := make([]byte, length)
	if _, err := io.ReadFull(r, data); err != nil {
		return nil, fmt.Errorf("read payload: %w", err)
	}
	var req Request
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("json: %w", err)
	}
	return &req, nil
}

// sendMessage writes a length-prefixed JSON message to stdout.
func sendMessage(w io.Writer, resp Response) {
	data, _ := json.Marshal(resp)
	binary.Write(w, binary.LittleEndian, uint32(len(data)))
	w.Write(data)
}

// ── Types ────────────────────────────────────────────────────────

type Request struct {
	Action string      `json:"action"`
	Params Params      `json:"params"`
	Target interface{} `json:"target"` // "local" or {"host":"...","user":"...","port":22,...}
}

type Params struct {
	BookURL string `json:"book_url,omitempty"`
	VolIDs  string `json:"vol_ids,omitempty"`
	Format  string `json:"format,omitempty"`
	Dest    string `json:"dest,omitempty"`
	VolType string `json:"vol_type,omitempty"`
	TaskID  string `json:"task_id,omitempty"`
	Wait    int    `json:"wait,omitempty"`
}

type SSHConfig struct {
	Host     string `json:"host"`
	User     string `json:"user,omitempty"`
	Port     int    `json:"port"`
	KeyFile  string `json:"keyFile,omitempty"`
	KmdrPath string `json:"kmdrPath,omitempty"`
}

type Response struct {
	Code   int         `json:"code"`
	Msg    string      `json:"msg"`
	Action string      `json:"action"`
	Data   interface{} `json:"data"`
}

// ── Input validation ─────────────────────────────────────────────

var (
	validActions = map[string]bool{
		"download": true, "status": true, "progress": true,
	}
	safeSchemes   = map[string]bool{"http": true, "https": true}
	volIDsRe      = regexp.MustCompile(`^[\d,]+$`)
	safeTaskIDRe  = regexp.MustCompile(`^[\w.-]+$`)
)

func validate(req *Request) error {
	if !validActions[req.Action] {
		return fmt.Errorf("Unknown action: %s", req.Action)
	}

	p := req.Params

	if req.Action == "download" {
		if p.BookURL == "" {
			return fmt.Errorf("book_url is required for download")
		}
		u, err := url.Parse(p.BookURL)
		if err != nil || !safeSchemes[u.Scheme] || u.Host == "" {
			return fmt.Errorf("Invalid book_url: %s", p.BookURL)
		}
		if !volIDsRe.MatchString(p.VolIDs) {
			return fmt.Errorf("Invalid vol_ids: %s", p.VolIDs)
		}
		if p.Dest != "" && (strings.HasPrefix(p.Dest, "-") || strings.Contains(p.Dest, "..")) {
			return fmt.Errorf("Invalid dest: %s", p.Dest)
		}
	}

	if req.Action == "progress" {
		if !safeTaskIDRe.MatchString(p.TaskID) {
			return fmt.Errorf("Invalid task_id: %s", p.TaskID)
		}
	}

	return nil
}

// ── Shell quoting helpers ────────────────────────────────────────

// shellQuote quotes a string for safe use in a POSIX shell command.
func shellQuote(s string) string {
	if s == "" {
		return "''"
	}
	// Safe characters: alphanumeric plus common path/token chars
	needsQuote := false
	for _, c := range s {
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') ||
			c == '_' || c == '-' || c == '.' || c == '/' || c == ':' || c == '@' || c == '%' || c == '+') {
			needsQuote = true
			break
		}
	}
	if !needsQuote {
		return s
	}
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}

// shellJoin builds a shell-safe command string from a list of arguments.
func shellJoin(args []string) string {
	quoted := make([]string, len(args))
	for i, a := range args {
		quoted[i] = shellQuote(a)
	}
	return strings.Join(quoted, " ")
}

// ── Command builder ──────────────────────────────────────────────

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
		cmd = append(cmd, "--wait", fmt.Sprintf("%d", req.Params.Wait))

	default:
		return nil, fmt.Errorf("unknown action: %s", req.Action)
	}

	return cmd, nil
}

// attachCommand appends the executed command to response data for diagnostics.
func attachCommand(data interface{}, cmd []string) interface{} {
	if m, ok := data.(map[string]interface{}); ok {
		m["_cmd"] = strings.Join(cmd, " ")
		return m
	}
	return data
}

// ── kmdr output parser ──────────────────────────────────────────

// parseKmdrOutput finds the last {"type":"result",...} line in NDJSON output.
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
		if t, _ := parsed["type"].(string); t == "result" {
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
	return Response{Code: 0, Msg: "success", Action: action, Data: nil}
}

// ── Local execution ──────────────────────────────────────────────

func runLocal(action string, cmd []string) Response {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	var stderr bytes.Buffer
	c := exec.CommandContext(ctx, cmd[0], cmd[1:]...)
	c.Stderr = &stderr

	stdout, err := c.Output()
	if err != nil {
		errMsg := strings.TrimSpace(stderr.String())
		if errMsg == "" {
			errMsg = err.Error()
		}
		if ctx.Err() == context.DeadlineExceeded {
			return Response{Code: 100, Msg: "命令执行超时", Action: action}
		}
		if exitErr, ok := err.(*exec.ExitError); ok {
			return Response{Code: exitErr.ExitCode(), Msg: errMsg, Action: action}
		}
		// exec.Error means the binary wasn't found
		return Response{Code: 101, Msg: "kmdr 未找到，请确认已安装 kmoe-manga-downloader", Action: action}
	}

	resp := parseKmdrOutput(action, string(stdout))
	resp.Data = attachCommand(resp.Data, cmd)
	return resp
}

// ── SSH execution ────────────────────────────────────────────────

func runSSH(action string, kmdrCmd []string, ssh SSHConfig) Response {
	if ssh.Host == "" {
		return Response{Code: 102, Msg: "SSH 目标主机未配置", Action: action}
	}
	if ssh.Port == 0 {
		ssh.Port = 22
	}

	target := ssh.Host
	if ssh.User != "" {
		target = ssh.User + "@" + ssh.Host
	}

	// Build remote command string
	var remoteCmd string
	if ssh.KmdrPath != "" {
		// Explicit kmdr path — replace "kmdr" and shell-join
		replaced := make([]string, len(kmdrCmd))
		copy(replaced, kmdrCmd)
		if len(replaced) > 0 && replaced[0] == "kmdr" {
			replaced[0] = ssh.KmdrPath
		}
		remoteCmd = shellJoin(replaced)
	} else {
		// Non-interactive SSH doesn't source .profile — use bash -lc
		remoteCmd = "bash -lc " + shellQuote(shellJoin(kmdrCmd))
	}

	// Build ssh command
	sshArgs := []string{
		"ssh",
		"-p", fmt.Sprintf("%d", ssh.Port),
		"-o", "ConnectTimeout=10",
		"-o", "BatchMode=yes",
	}
	if ssh.KeyFile != "" {
		sshArgs = append(sshArgs, "-i", ssh.KeyFile, "-o", "IdentitiesOnly=yes")
	}
	sshArgs = append(sshArgs, target, remoteCmd)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	var stderr bytes.Buffer
	c := exec.CommandContext(ctx, sshArgs[0], sshArgs[1:]...)
	c.Stderr = &stderr

	stdout, err := c.Output()
	if err != nil {
		errMsg := strings.TrimSpace(stderr.String())
		if errMsg == "" {
			errMsg = err.Error()
		}
		if ctx.Err() == context.DeadlineExceeded {
			return Response{Code: 100, Msg: "SSH 命令执行超时", Action: action}
		}

		hint := ""
		switch {
		case strings.Contains(errMsg, "Permission denied"):
			hint = " (SSH 认证失败。如果密钥有密码保护，请先用 ssh-agent 加载密钥：\n" +
				"   Windows: 启动 OpenSSH Authentication Agent 服务，然后 ssh-add <密钥路径>\n" +
				"   macOS:   ssh-add --apple-use-keychain <密钥路径>\n" +
				"   Linux:   ssh-add <密钥路径>\n" +
				"   或在扩展设置中指定密钥文件路径)"
		case strings.Contains(errMsg, "Could not resolve") ||
			strings.Contains(errMsg, "Name or service not known"):
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

// ── Request handler ──────────────────────────────────────────────

func handleRequest(req *Request) Response {
	if err := validate(req); err != nil {
		return Response{Code: 103, Msg: err.Error(), Action: req.Action}
	}

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
		ssh := SSHConfig{Port: 22}
		if host, ok := target["host"].(string); ok && host != "" {
			ssh.Host = host
		} else {
			return Response{Code: 104, Msg: "SSH target missing host", Action: req.Action}
		}
		if user, ok := target["user"].(string); ok {
			ssh.User = user
		}
		if port, ok := target["port"].(float64); ok {
			ssh.Port = int(port)
		}
		if keyFile, ok := target["keyFile"].(string); ok {
			ssh.KeyFile = keyFile
		}
		if kmdrPath, ok := target["kmdrPath"].(string); ok {
			ssh.KmdrPath = kmdrPath
		}
		return runSSH(req.Action, cmd, ssh)

	default:
		return Response{Code: 104, Msg: "invalid target config", Action: req.Action}
	}
}

// ── Main ─────────────────────────────────────────────────────────

func main() {
	// Disable stdout buffering — native messaging must be synchronous
	// (Go's os.Stdout is unbuffered by default, but we use it directly)

	reader := io.Reader(os.Stdin)

	for {
		req, err := readMessage(reader)
		if err == io.EOF {
			break
		}
		if err != nil {
			sendMessage(os.Stdout, Response{
				Code: 200, Msg: fmt.Sprintf("read error: %v", err),
			})
			break
		}

		resp := handleRequest(req)
		sendMessage(os.Stdout, resp)
	}
}
