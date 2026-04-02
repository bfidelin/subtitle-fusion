from pathlib import Path

from src.imdb_index import IMDbIndex
from src.models import MediaContext


def test_imdb_index_loads_basics_and_candidates(tmp_path: Path) -> None:
    imdb_dir = tmp_path / "imdb"
    imdb_dir.mkdir()
    (imdb_dir / "title.basics.tsv").write_text(
        "tconst\tprimaryTitle\n"
        "tt123\tExample Show\n",
        encoding="utf-8",
    )
    (imdb_dir / "name.basics.tsv").write_text(
        "nconst\tprimaryName\n"
        "nm1\tJean Dupont\n",
        encoding="utf-8",
    )
    (imdb_dir / "title.principals.tsv").write_text(
        "tconst\tnconst\tcharacters\n"
        "tt123\tnm1\t[\"Commissaire Morel\"]\n",
        encoding="utf-8",
    )

    index = IMDbIndex.from_dir(imdb_dir)
    media = MediaContext(imdb_title_id="tt123")

    title_candidates = index.get_title_candidates(media)
    people = index.get_people_for_title("tt123")
    characters = index.get_characters_for_title("tt123")

    assert title_candidates[0].name == "Example Show"
    assert people[0].name == "Jean Dupont"
    assert characters[0].name == "Commissaire Morel"
