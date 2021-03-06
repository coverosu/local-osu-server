import utils
import orjson
import queries
import packets
import asyncio
from ext import glob
from typing import Union
from typing import Optional
from objects.mods import Mods

SCORES = list[dict]
RANKED_PLAYS = dict[str, list[dict]]
APPROVED_PLAYS = RANKED_PLAYS
OSU_DAILY_API = 'https://osudaily.net/api'

class Player:
    def __init__(
        self, name: str, 
        from_login: bool = False
    ) -> None:
        self.name = name
        self.from_login = from_login
        if (
            name not in glob.profiles
            and from_login
        ):
            self.init_db()

        self.queue = bytearray()

        self.rank: int = 9999999
        self.acc: float = 0.0
        self.playcount: int = 0
        self.total_score: int = 0
        self.ranked_score: int = 0
        self.pp: Union[float, int] = 0

        # constants
        self.mode = 0
        self.mods = 0
        self.userid = 2
        self.action = 0
        self.map_id = 0
        self.country = 0
        self.map_md5 = ''
        self.utc_offset = 0
        self.info_text = ''
        self.location = (0.0, 0.0)
        self.bancho_privs = 63

    def clear(self) -> bytearray:
        _queue = self.queue.copy()
        self.queue.clear()
        return _queue

    def init_db(self) -> None:
        if (
            not glob.pfps or
            self.name not in glob.pfps or
            glob.pfps[self.name] is None
        ):
            glob.pfps.update({self.name: None})

        if (
            not glob.profiles or
            self.name not in glob.profiles
        ):
            glob.profiles.update(
                queries.init_profile(self.name)
            )

        utils.update_files()
        glob.current_profile = glob.profiles[self.name]

    async def get_rank(self) -> Optional[int]:
        if not glob.config.osu_daily_api_key:
            return 1

        url = f'{OSU_DAILY_API}/pp.php'
        params = {
            'k': glob.config.osu_daily_api_key,
            't': 'pp',
            'v': self.pp,
            'm': self.mode
        }

        async with glob.http.get(url, params=params) as resp:
            if not resp or resp.status != 200:
                return 1

            json = orjson.loads(await resp.content.read())
            if not json:
                return 1

        if (
            'error' in json and
            json['error'] == 'Only 1 request per second is authorized'
        ):
            raise Exception

        if 'rank' not in json:
            return 1

        return json['rank']

    async def update(
        self, filter_mod: Optional[Mods] = None
    ) -> None:
        scores: SCORES = []

        if not glob.current_profile:
            glob.current_profile = glob.profiles[self.name]

        ranked_plays: Optional[RANKED_PLAYS] = \
        glob.current_profile['plays']['ranked_plays']

        approved_plays: Optional[APPROVED_PLAYS] = \
        glob.current_profile['plays']['approved_plays']

        for plays in (ranked_plays, approved_plays):
            if plays:
                for v in plays.values():
                    scores.extend(v)

        if filter_mod:
            scores = [
                x for x in scores if
                x['mods'] & filter_mod
            ]
        else:
            scores = [
                x for x in scores if
                not x['mods'] & (Mods.RELAX | Mods.AUTOPILOT)
            ]

        if glob.config.disable_funorange_maps:
            scores = [
                x for x in scores if 
                x['md5'] not in glob.modified_beatmaps
            ]

        scores.sort(key = lambda s: s['pp'], reverse = True)
        top_scores = utils.filter_top_scores(scores[:100])
        top_scores.sort(key = lambda s: s['pp'], reverse = True)

        pp = sum([s['pp'] * 0.95 ** i for i, s in enumerate(top_scores)])
        pp += 416.6667 * (1 - (0.9994 ** len(scores)))
        self.pp = round(pp)

        # TODO: figure out how acc calc is wrong
        # for now use old method
        if top_scores:
            self.acc = sum([s['acc'] for s in top_scores]) / len(top_scores)
            # acc = sum([s['acc'] * 0.95 ** i for i, s in enumerate(top_scores)])
            # bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(scores)))
            # self.acc = (acc * bonus_acc) / 100

        if 'playcount' in glob.current_profile:
            self.playcount = glob.current_profile['playcount']

        rank = None
        updated_rank = False
        while not updated_rank:
            try: 
                rank = await self.get_rank()
                updated_rank = True
            except: 
                await asyncio.sleep(1)
        
        if rank:
            self.rank = rank

        if self.from_login:
            self.queue += packets.userStats(self)