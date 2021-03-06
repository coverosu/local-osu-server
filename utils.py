import base64
import orjson
import asyncio
import hashlib
import colorama
import subprocess
from typing import Any
import pyttanko as oppai
from typing import Union
from pathlib import Path
from colorama import Fore
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from objects.config import Config

if TYPE_CHECKING:
    from objects import Score
    from objects import Beatmap
    from objects import BanchoScore
    from objects import ModifiedBeatmap

try:
    import packets
except ImportError:
    pass

try:
    from ext import glob
except ImportError:
    pass

colorama.init(autoreset=True)

Color = Fore

PP = float
ACCURACY = float
SCORE = Union['Score', 'BanchoScore']
def calculator(
    score: SCORE, bmap: Union['Beatmap', 'ModifiedBeatmap', oppai.beatmap],
    stars: Optional[oppai.diff_calc] = None
) -> tuple[PP, ACCURACY]:
    """PP calculator (easy to work with and change whenever needed)"""
    if not isinstance(bmap, oppai.beatmap):
        file = bmap.map_file
    else:
        file = bmap

    if 'BanchoScore' not in str(type(score)): # avoids merge conflicts
        if not stars:
            stars = oppai.diff_calc().calc(file, score.mods) # type: ignore

        pp, *_, acc_percent = oppai.ppv2(
            aim_stars = stars.aim,
            speed_stars = stars.speed,
            bmap = file,
            mods = score.mods, # type: ignore
            n300 = score.n300, # type: ignore
            n100 = score.n100, # type: ignore
            n50 = score.n50, # type: ignore
            nmiss = score.nmiss, # type: ignore
            combo = score.max_combo # type: ignore
        )
    else:
        mods = int(score.enabled_mods) # type: ignore
        if not stars:
            stars = oppai.diff_calc().calc(file, mods)

        pp, *_, acc_percent = oppai.ppv2(
            aim_stars = stars.aim,
            speed_stars = stars.speed,
            bmap = file,
            mods = mods,
            n300 = int(score.count300), # type: ignore
            n100 = int(score.count100), # type: ignore
            n50 = int(score.count50), # type: ignore
            nmiss = int(score.countmiss), # type: ignore
            combo = int(score.maxcombo) # type: ignore
        )

        score.pp = pp

    return (pp, acc_percent)

def is_path(p: str) -> Union[Path, Literal[False]]:
    path = Path(p)

    if path.is_file():
        return path
    else:
        return False

def update_files() -> None:
    glob.pfps.update_file()
    glob.beatmaps.update_file()
    glob.profiles.update_file()
    glob.json_config.update_file()
    glob.modified_beatmaps.update_file()

async def _add_to_player_queue(packets: bytes) -> None:
    while not glob.player:
        await asyncio.sleep(1)

    glob.player.queue += packets

def add_to_player_queue(packets: bytes) -> None:
    """Safe way to add to a player's queue"""
    asyncio.create_task(_add_to_player_queue(packets))

def filter_top_scores(_scores: list[dict]) -> list[dict]:
    """Removes duplicated scores"""
    md5s = []
    scores = []
    for s in _scores:
        if s['md5'] not in md5s:
            md5s.append(s['md5'])
            scores.append(s)

    return scores

def log(*message: str, color: str = Color.WHITE) -> None:
    print(f"{color}{' '.join(message)}")
    return

log_error = lambda *m: log(*m, color = Color.RED)
log_success = lambda *m: log(*m, color = Color.GREEN)

def bytes_to_string(b: bytes) -> str:
    return base64.b64encode(b).decode('ascii')

def string_to_bytes(s: str) -> bytes:
    return base64.b64decode(s.encode('ascii'))

async def async_str_to_wslpath(path: str) -> Path:
    wslpath_proc = await asyncio.subprocess.create_subprocess_exec(
        'wslpath', path,
        stdin = asyncio.subprocess.DEVNULL,
        stdout = asyncio.subprocess.PIPE,
        stderr = asyncio.subprocess.DEVNULL,
    )
    stdin, _ = await wslpath_proc.communicate()

    return Path(stdin.decode().removesuffix('\n'))

def str_to_wslpath(path: str) -> Path:
    process = subprocess.run(
        f'wslpath {path}',
        stdout = subprocess.PIPE,
        stderr = subprocess.DEVNULL,
    )
    return Path(process.stdout.decode().removesuffix('\n'))

def delete_keys(_dict: dict, *keys: str) -> dict:
    _dict_copy = _dict.copy()
    for k in keys:
        try: del _dict_copy[k]
        except: pass

    return _dict_copy

def local_message(
    message: str, 
    channel: str = '#osu'
) -> bytes:
    return packets.sendMsg(
        client = 'local',
        msg = message,
        target = channel,
        userid = -1,
    )

def get_grade(
    score: Optional['Score'] = None, 
    n300: Optional[int] = None,
    n100: Optional[int] = None,
    n50: Optional[int] = None,
    nmiss: Optional[int] = None,
    mods: Optional[int] = None
    ) -> str:
    if score:
        total = score.n300 + score.n100 + score.n50 + score.nmiss
        n300_percent = score.n300 / total
        using_hdfl = score.mods & 1032
        nomiss = score.nmiss == 0
        n50 = score.n50
    else:
        total = n300 + n100 + n50 + nmiss # type: ignore
        n300_percent = n300 / total
        using_hdfl = mods & 1032 # type: ignore
        nomiss = nmiss == 0
        n50 = n50

    if n300_percent > 0.9:
        if nomiss and (n50 / total) < 0.1: # type: ignore
            return 'SH' if using_hdfl else 'S'
        else:
            return 'A'

    if n300_percent > 0.8:
        return 'A' if nomiss else 'B'

    if n300_percent > 0.7:
        return 'B' if nomiss else 'C'

    if n300_percent > 0.6:
        return 'C'

    return 'D'

def altered_input(prompt: str, lower: bool = False) -> str:
    if lower:
        return input(prompt).strip().lower()
    
    return input(prompt).strip()

def bool_input(prompt: str) -> bool:
    return altered_input(prompt, lower = True).startswith('y')

def setup_config() -> Config:
    config = Config()

    print('remember to continue click enter!')
    for prompt, key in (
        ('Please enter your osu! folder path\n>> ', 'osu_path'),
        ('Please enter your songs folder path\nnote you can type `None` if your songs folder is in your osu! folder\n>> ', 'songs'),
        ('Please enter your replay folder path\nnote you can type `None` if your replay folder is in your osu! folder\n>> ', 'replay'),
        ('Please enter your screenshots folder path\nnote you can type `None` if your screenshots folder is in your osu! folder\n>> ', 'screenshots')
    ):
        while True:
            raw_input = altered_input(prompt)

            if raw_input == 'None':
                config.paths[key] = None
                break
            
            path_str = Path(raw_input)
            
            if glob.using_wsl:
                path_str = str_to_wslpath(str(path_str))
            
            if not path_str.exists():
                input('invalid path!\nclick enter to continue')
                continue
                
            config.paths[key] = str(path_str)
            break

    config.pp_leaderboard = bool_input(
        '(yes or no)\n'
        'Show pp values for each score on leaderboard (PP leaderboards)\n'
        'WARNING REALLY SLOW RIGHT NOW SO PLEASE ENTER N\n>> '
    )
    config.ping_user_when_recent_score = bool_input(
        '(yes or no)\n'
        'Highlight me when I submit any score\n>> '
    )
    
    if bool_input('(yes or no)\nmenu icon?\n>> '):
        config.menu_icon['image_link'] = altered_input(
            'image link\n>> '
        )
        config.menu_icon['click_link'] = altered_input(
            'click link\n>> '
        )
    
    config.command_prefix = altered_input(
        'command prefix\ndefault: !\n>> ',
        lower = True
    ) or '!'

    config.show_pp_for_personal_best = bool_input(
        '(yes or no)\n'
        'Show pp for personal best (fast)\n>> '
    )

    while True: 
        try:
            config.amount_of_scores_on_lb = int(input(
                'Number of scores shown on leaderboard\nmaximum: 100\n>> '
            ))
            break
        except:
            continue
    
    config.auto_update = bool_input(
        '(yes or no)\n'
        'Enable auto updater?\n>> '
    )

    config.disable_funorange_maps = bool_input(
        '(yes or no)\n'
        'Disable osu!trainer (funorange) maps?\n>> '
    )

    config.seasonal_bgs = altered_input(
        'Seasonal Backgrounds! (Ingame backgrounds)\n'
        'To apply just paste the link to a background\n'
        'To have multiple seperate each link with a comma\n'
        'To have non just click enter\n'
        '>> '
    ).split(',')

    osu_api_doc = (
        'osu! api key\n'
        'Needed throughout the whole server really\n'
        'You can find your api key here https://old.ppy.sh/p/api/\n'
        "Type `None` if you can't get one (server won't really be able to function)"
    )
    imgur_doc = (
        'Imgur client id\n'
        'If u want your screenshots to be uploaded to imgur when "shift + screenshot_key"\n'
        'You will have to provide a client id which you can find here https://api.imgur.com/\n'
        "Type `None` if you don't want screenshots to be uploaded"
    )
    osu_daily_api_doc = (
        'osu! daily api key\n'
        'If you want your bancho rank to show up ingame\n'
        'you will need this api key which you can find here https://github.com/Adrriii/osudaily-api/wiki\n'
        'Type `None` if you want your rank to show as 1 the whole time'    
    )
    username_doc = (
        'osu! username\n'
        'If you want direct working this is needed\n'
        'Type `None` if you want direct/bmap downloading not to work'
    )
    password_doc = (
        'osu! password\n'
        'If you want direct working this is needed\n'
        'Type `None` if you want direct/bmap downloading not to work'
    )

    md5s = ('osu_api_key', 'osu_daily_api_key', 'osu_password')

    for prompt, key in (
        (osu_api_doc, 'osu_api_key'),
        (imgur_doc, 'imgur_client_id'),
        (osu_daily_api_doc, 'osu_daily_api_key'),
        (username_doc, 'osu_username'),
        (password_doc, 'osu_password')
    ):
        while True:
            value = altered_input(f'{prompt}\n>> ')
            if value == 'None':
                config.__dict__[key] = None
                break
        
            if key in md5s:
                if key == 'osu_password':
                    value = hashlib.md5(value.encode()).hexdigest()
                else:
                   if len(value) < 32:
                        input('invalid value was entered\nclick enter to retry')
                        continue

            config.__dict__[key] = value
            break
    
    return config

def real_type(value: str) -> Any:
    if value.replace('-', '', 1).isdecimal():
        return int(value)
    
    try: return float(value)
    except: pass

    try:
        return orjson.loads(value)
    except:
        return value

NONE_FILE = Path('none'*1000)