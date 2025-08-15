from typing import Optional

def resolve_volume(volume: str) -> Optional[set[int]]:
    if volume == 'all':
        return None

    if ',' in volume:
        # 如果使用分隔符
        volumes = volume.split(',')
        volumes = [resolve_volume(v) for v in volumes]

        ret = set()
        for v in volumes:
            if v is not None:
                ret.update(v)

        return ret

    if (volume := volume.strip()).isdigit():
        # 只有一个数字
        assert (volume := int(volume)) > 0, "Volume number must be greater than 0."
        return {volume}
    elif '-' in volume and volume.count('-') == 1 and ',' not in volume:
        # 使用了范围符号
        start, end = volume.split('-')

        assert start.strip().isdigit() and end.strip().isdigit(), "Invalid range format. Use 'start-end' or 'start, end'."

        start = int(start.strip())
        end = int(end.strip())

        assert start > 0 and end > 0, "Volume numbers must be greater than 0."
        assert start <= end, "Start of range must be less than or equal to end."

        return set(range(start, end + 1))

    raise ValueError(f"Invalid volume format: {volume}. Use 'all', '1,2,3', '1-3', or '1-3,4-6'.")