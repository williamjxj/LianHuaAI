"""画师风格管理 — 21位古典连环画大师的风格特征"""

from src.models import ARTIST_STYLE_DESCRIPTIONS, ArtistStyle


class StyleManager:
    """画师风格管理器"""

    @staticmethod
    def get_style_keywords(artist: ArtistStyle) -> str:
        """获取画师风格的关键词描述

        Args:
            artist: 画师枚举

        Returns:
            风格描述文本
        """
        return ARTIST_STYLE_DESCRIPTIONS.get(artist, "")

    @staticmethod
    def get_all_artists() -> list[ArtistStyle]:
        """获取所有画师列表"""
        return ArtistStyle.list_all()
