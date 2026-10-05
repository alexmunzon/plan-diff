"""PR 9: unzip a fetched CMS file safely (review 1 finding 6). Zips are built in tmp_path."""

import stat
import zipfile
from pathlib import Path

import pytest

from plan_diff.cms.unzip import MARKER, UnzipRefused, unzip_cms


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return path


def test_extracts_into_a_sibling_folder_and_skips_an_unchanged_zip(tmp_path: Path) -> None:
    zipped = make_zip(
        tmp_path / "pbp-2026.zip", {"pbp_Section_D.txt": b"a\tb\n", "sub/x.txt": b"x"}
    )
    folder, changed = unzip_cms(zipped)
    assert changed and folder == tmp_path / "pbp-2026"
    assert (folder / "pbp_Section_D.txt").read_bytes() == b"a\tb\n"
    assert (folder / "sub" / "x.txt").read_bytes() == b"x"
    assert unzip_cms(zipped) == (folder, False)
    make_zip(zipped, {"new.txt": b"n"})  # a new download with a new hash replaces the folder
    assert unzip_cms(zipped) == (folder, True)
    assert sorted(p.name for p in folder.iterdir()) == [MARKER, "new.txt"]
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".part")] == []


@pytest.mark.parametrize(
    "name", ["../evil.txt", "/etc/evil.txt", "a/../../evil.txt", "C:/evil.txt"]
)
def test_refuses_zip_slip(tmp_path: Path, name: str) -> None:
    zipped = make_zip(tmp_path / "bad.zip", {"ok.txt": b"ok", name: b"evil"})
    with pytest.raises(UnzipRefused, match="outside the folder"):
        unzip_cms(zipped)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.zip"]


def test_refuses_a_symlink_member(tmp_path: Path) -> None:
    zipped = tmp_path / "link.zip"
    with zipfile.ZipFile(zipped, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "/etc/passwd")
    with pytest.raises(UnzipRefused, match="symlink"):
        unzip_cms(zipped)


def test_refuses_too_many_members_and_too_many_bytes(tmp_path: Path) -> None:
    many = make_zip(tmp_path / "many.zip", {f"{i}.txt": b"x" for i in range(4)})
    with pytest.raises(UnzipRefused, match="4 members"):
        unzip_cms(many, max_members=3)
    big = make_zip(tmp_path / "big.zip", {"zeros.txt": b"0" * 10_000})
    with pytest.raises(UnzipRefused, match="uncompressed"):
        unzip_cms(big, max_bytes=9_999)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["big.zip", "many.zip"]


def test_never_deletes_a_folder_it_did_not_make(tmp_path: Path) -> None:
    zipped = make_zip(tmp_path / "pbp.zip", {"a.txt": b"a"})
    (tmp_path / "pbp").mkdir()
    (tmp_path / "pbp" / "notes.txt").write_text("mine")
    with pytest.raises(UnzipRefused, match="not made by unzip"):
        unzip_cms(zipped)
    assert (tmp_path / "pbp" / "notes.txt").read_text() == "mine"
