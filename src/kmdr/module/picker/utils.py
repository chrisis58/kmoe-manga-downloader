from typing import Optional

from kmdr.core.error import ArgsResolveError

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
        if (volume_digit := int(volume)) <= 0:
            raise ArgsResolveError(f"卷号必须大于 0，当前值为 {volume_digit}。")
        return {volume_digit}
    elif '-' in volume and volume.count('-') == 1 and ',' not in volume:
        # 使用了范围符号
        start, end = volume.split('-')

        if not start.strip().isdigit() or not end.strip().isdigit():
            raise ArgsResolveError(f"无效的范围格式: {volume}。请使用 'start-end' 或 'start, end'。")

        start = int(start.strip())
        end = int(end.strip())

        if start <= 0:
            raise ArgsResolveError(f"卷号必须大于 0，当前值为 {start}。")
        if end <= 0:
            raise ArgsResolveError(f"卷号必须大于 0，当前值为 {end}。")
        if start > end:
            raise ArgsResolveError(f"起始卷号必须小于或等于结束卷号，当前值为 {start} - {end}。")

        return set(range(start, end + 1))

    raise ArgsResolveError(f"无效的卷号格式: {volume}。请使用 'all', '1,2,3', '1-3', 或 '1-3,4-6'。")