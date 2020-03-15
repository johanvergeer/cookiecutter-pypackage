import json
import re
from typing import List, Tuple

import pytest

# @pytest.mark.datafiles("cookiecutter.json", relative_to=ROOT_DIR)
from tests.utils import PROJECT_ROOT_DIR


def get_prompts_from_cookiecutter_json() -> List[str]:
    with open(str((PROJECT_ROOT_DIR / "cookiecutter.json"))) as f:
        keys = list(json.load(f).keys())
        return keys


def get_prompts_from_doc() -> List[str]:
    prompt_regex = re.compile(r"\n`[`a-z_]+`")
    with open(str(PROJECT_ROOT_DIR / "docs" / "prompts.rst")) as f:
        raw_prompts_from_doc = prompt_regex.findall("\n".join(f.readlines()))
        return [p.replace("`", "").replace("\n", "") for p in raw_prompts_from_doc]


def get_indexes(*prompts: List[str]) -> List[int]:
    length = max([len(p) for p in prompts])
    return [i for i in range(length)]


def fill_prompts_list(prompts: List[str], length: int) -> None:
    if len(prompts) < length:
        prompts.extend(["None"] * (length - len(prompts)))


def get_prompts() -> List[Tuple[int, str, str]]:
    from_json = get_prompts_from_cookiecutter_json()
    from_doc = get_prompts_from_doc()
    indexes = get_indexes(from_json, from_doc)

    fill_prompts_list(from_json, len(indexes))
    fill_prompts_list(from_doc, len(indexes))

    return list(zip(indexes, from_json, from_doc))


@pytest.mark.parametrize("index,from_json,from_doc", get_prompts())
def test_cookiecutter_prompts_are_documented(
    index: int, from_json: str, from_doc: str
) -> None:
    assert (
        from_json == from_doc
    ), f"Prompt {index} should be '{from_json}' but is '{from_doc}'"
