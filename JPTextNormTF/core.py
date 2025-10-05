import re
import calendar
import unicodedata
from typing import Optional

class DateNormalizer:
    """Japanese number and date normalizer"""

    KANJI_NUM = {'零':0,'〇':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    UNIT_SMALL = {'十':10,'百':100,'千':1000}
    UNIT_LARGE = {'万':10**4, '億':10**8, '兆':10**12}

    ERA_MAP = {
        "令和": 2019, "平成": 1989, "昭和": 1926, "大正": 1912, "明治": 1868,
    }
    ERA_ABBR_MAP = {"R": 2019, "H": 1989, "S": 1926, "T": 1912, "M": 1868}
    FW_MAP = str.maketrans("０１２３４５６７８９", "0123456789")

    @classmethod
    def parse_small(cls, s: str) -> int:
        total, num = 0, 0
        for ch in s:
            if ch in cls.KANJI_NUM:
                num = cls.KANJI_NUM[ch]
            elif ch in cls.UNIT_SMALL:
                unit = cls.UNIT_SMALL[ch]
                if num == 0:
                    num = 1
                total += num * unit
                num = 0
        total += num
        return total

    @classmethod
    def kanji_to_int(cls, s: str) -> int:
        if not s:
            return 0
        has_unit = any((ch in cls.UNIT_SMALL) or (ch in cls.UNIT_LARGE) for ch in s)
        if has_unit:
            total, current = 0, ''
            for ch in s:
                if ch in cls.UNIT_LARGE:
                    val = cls.parse_small(current)
                    if val == 0:
                        val = 1
                    total += val * cls.UNIT_LARGE[ch]
                    current = ''
                else:
                    current += ch
            total += cls.parse_small(current)
            return total
        else:
            digits = []
            for ch in s:
                if ch in cls.KANJI_NUM:
                    digits.append(str(cls.KANJI_NUM[ch]))
                elif ch.isdigit():
                    digits.append(ch)
            return int(''.join(digits)) if digits else 0

    @classmethod
    def normalize_number(cls, s: str) -> int:
        if s == "元":
            return 1
        if re.fullmatch(r"\d+", s):
            return int(s)
        return cls.kanji_to_int(s)

    @classmethod
    def replace_dates(cls, text: str) -> str:
        kanji_num_chars = r"[元\d一二三四五六七八九十百〇]"
        # --- 各種日付パターンを順に置換 ---
        def sub(pattern, repl, txt):
            return re.compile(pattern).sub(repl, txt)

        def _make_repl(era_year, month, day_str, era_base=None):
            year = cls.normalize_number(era_year)
            if era_base:
                year = era_base + year - 1
            month = cls.normalize_number(month)
            if day_str == "末日":
                day = calendar.monthrange(year, month)[1]
            else:
                day = cls.normalize_number(day_str[:-1])
            return f"{year:04d}-{month:02d}-{day:02d}"

        # 和暦表記
        def era_repl(m):
            era, y, mth, d = m.groups()
            return _make_repl(y, mth, d, cls.ERA_MAP[era])
        text = sub(r"(明治|大正|昭和|平成|令和)"+rf"({kanji_num_chars}+)年({kanji_num_chars}+)月(末日|{kanji_num_chars}+日)", era_repl, text)

        # 西暦表記
        def seireki_repl(m):
            y, mth, d = m.groups()
            return _make_repl(y, mth, d)
        text = sub(r"([０-９\d〇一二三四五六七八九十百千]{2,4})年"+rf"({kanji_num_chars}+)月(末日|{kanji_num_chars}+日)", seireki_repl, text)

        # 略号 (R5.3.2)
        def abbr_repl(m):
            era_abbr, y, mth, d = m.groups()
            return _make_repl(y, mth, d, cls.ERA_ABBR_MAP[era_abbr])
        text = sub(r"([RHSTM])([元\d]+)[年./](\d{1,2})[月./](末日|\d{1,2})日?", abbr_repl, text)

        # 区切り型
        text = re.sub(r"(\d{4})[./](\d{1,2})[./](\d{1,2})",
                      lambda m: f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}",
                      text)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """全角→半角、日付→ISO、漢数字→算用数字"""
        text = text.translate(cls.FW_MAP)
        text = cls.replace_dates(text)
        return text




class TextCleaner:
    """
    高度な日本語テキストクリーニングクラス。

    主な機能:
    - 全角→半角変換 (NFKC)
    - 記号・括弧・絵文字の除去
    - URL・メンション・ハッシュタグ除去
    - 空白の統一
    """

    def __init__(self, keep_emojis: bool = False):
        """
        Args:
            keep_emojis (bool): Trueなら絵文字を残す。
        """
        self.keep_emojis = keep_emojis

    # --- 基本正規化 ---
    @staticmethod
    def normalize_str(s: str) -> str:
        """
        全角英数字・カタカナ・スペースを半角に統一。
        """
        if not isinstance(s, str):
            return ""
        return unicodedata.normalize("NFKC", s)

    # --- 記号除去 ---
    @staticmethod
    def remove_symbols(s: str) -> str:
        """
        括弧類をスペースに、その他の特殊記号を削除。
        """
        if not isinstance(s, str):
            return ""
        s = re.sub(r'[「」【】『』［］〈〉《》〔〕（）()]', ' ', s)
        s = re.sub(r'[●■※◆◇☆★○◎◇◆→←↑↓■□]', '', s)
        return s

    # --- URL除去 ---
    @staticmethod
    def remove_urls(s: str) -> str:
        """
        URL(http://, https://)を削除。
        """
        if not isinstance(s, str):
            return ""
        return re.sub(r'https?://\S+', '', s)

    # --- 絵文字除去 ---
    @staticmethod
    def remove_emojis(s: str) -> str:
        """
        絵文字を削除（Unicode範囲指定）。
        """
        emoji_pattern = re.compile(
            '['
            '\U0001F600-\U0001F64F'  # emoticons
            '\U0001F300-\U0001F5FF'  # symbols & pictographs
            '\U0001F680-\U0001F6FF'  # transport & map symbols
            '\U0001F1E0-\U0001F1FF'  # flags
            '\U0001F900-\U0001F9FF'  # supplemental pictographs
            '\u2600-\u26FF'          # misc symbols
            '\u2700-\u27BF'          # dingbats
            '\uFE0F'                 # variation selectors
            ']+', flags=re.UNICODE
        )
        return emoji_pattern.sub('', s)

    # --- 空白統一 ---
    @staticmethod
    def unify_whitespaces(s: str) -> str:
        """
        改行・タブ・全角空白などを単一半角スペースに統一。
        """
        if not isinstance(s, str):
            return ""
        return re.sub(r'\s+', ' ', s).strip()

    # --- メンション/ハッシュタグ削除 ---
    @staticmethod
    def remove_mentions_and_hashtags(s: str) -> str:
        """
        @ユーザー名 / #タグ を削除。
        """
        if not isinstance(s, str):
            return ""
        s = re.sub(r'@[\w\-\u3000-\u9FFF]+', '', s)
        s = re.sub(r'#[\w\-\u3000-\u9FFF]+', '', s)
        return s

    # --- 総合クリーニング ---
    def clean(self, s: Optional[str]) -> str:
        """
        全処理を統合的に実行。

        Returns:
            str: 正規化・記号除去・空白統一後の文字列
        """
        if not isinstance(s, str):
            return ""

        s = self.normalize_str(s)
        s = self.remove_urls(s)
        s = self.remove_mentions_and_hashtags(s)
        s = self.remove_symbols(s)
        if not self.keep_emojis:
            s = self.remove_emojis(s)
        s = self.unify_whitespaces(s)
        return s
