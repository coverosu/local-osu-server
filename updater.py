import sys
import asyncio
from ext import glob
from pathlib import Path
from typing import Optional
from utils import log_error
from utils import log_success
import version as local_version

VERSION_LINK = (
    'https://raw.githubusercontent.com/coverosu/local-osu-server/main/version.py'
)

file_structure_typing = Optional[dict[str, list[str]]]
FILE_STRUCTURE: file_structure_typing = None

async def needs_updating() -> bool:
    global FILE_STRUCTURE
    async with glob.http.get(VERSION_LINK) as resp:
        if not resp:
            log_error('no version file found on github')
            return False

        if resp.status != 200:
            log_error('no version file found on github')
            return False

        exec(await resp.text())
        github_version: str = locals()['version']

    if github_version == local_version.version:
        log_success('server up to date!')
        return False
    else:
        log_success('server needs updating, updating server.')
        FILE_STRUCTURE = {
            'files': locals()['file_structure'],
            'deleted_files': locals()['deleted_files']
        }
        return True

BASE_URL = 'https://raw.githubusercontent.com/coverosu/local-osu-server/main'

async def update() -> None:
    global FILE_STRUCTURE
    if not FILE_STRUCTURE:
        log_error("couldn't update")
        return

    for type, fstructure in FILE_STRUCTURE.items():
        for path_str in fstructure:
            if type == 'files' and '.' in path_str:
                async with glob.http.get(
                    f'{BASE_URL}/{path_str}'
                ) as resp:
                    if not resp or resp.status != 200:
                        log_error(f"couldn't get content for {path_str}")
                        continue

                    file_content = await resp.content.read()

            split_path = path_str.split('/')
            path = Path.cwd() / split_path[0]
            for p in split_path[1:]:
                if (
                    '.' not in path.suffix and
                    not path.exists() and
                    type == 'files'
                ):
                    path.mkdir(exist_ok=True)

                path = path / p

            if type == 'files' and '.' in path_str:
                path.write_bytes(file_content) # type: ignore
                log_success(f"successfully updated file {path_str}")
            elif type == 'deleted_files':
                try: path.unlink()
                except: pass
                log_success(f"successfully deleted file {path_str}")
            else:
                log_success(f"successfully created path {path_str}")
            
            if 'requirements.txt' in path_str:
                await asyncio.create_subprocess_shell(
                    f'{sys.executable} -m pip install -r requirements.txt',
                    stdin = asyncio.subprocess.DEVNULL,
                    stderr = asyncio.subprocess.DEVNULL,
                    stdout = asyncio.subprocess.DEVNULL
                )

                log_success('updated packages!')

    log_success((
        'successfully updated the server!\n'
        'restart the server to run again!'
    ))