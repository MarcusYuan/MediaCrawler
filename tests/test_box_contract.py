# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tests/test_box_contract.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""Plugin Box 机器输出合同的黑盒与单元测试。

黑盒用例即 Catalog 准入所需的"可确定性解析的成功/失败样例"：
- --version 精确裸 semver（对齐 plugin-box version_contract 断言）
- doctor --json 可解析且 ok
- 机器模式下参数错误 / 缺登录态输出失败 envelope 与稳定退出码
"""

import json
import os
import re
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from tools import box_contract  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_mode():
    box_contract.set_machine_mode(False)
    box_contract._ENVELOPE_EMITTED = False
    yield
    box_contract.set_machine_mode(False)
    box_contract._ENVELOPE_EMITTED = False


def run_cli(*args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# 单元测试：envelope / 退出码 / 统计 / 路径推导
# ---------------------------------------------------------------------------

class TestEnvelope:
    def test_success_envelope_shape(self, capsys):
        box_contract.output_envelope(result={"a": 1})
        doc = json.loads(capsys.readouterr().out)
        assert doc["contract_version"] == "1"
        assert doc["ok"] is True
        assert doc["result"] == {"a": 1}

    def test_error_envelope_shape(self, capsys):
        err = box_contract.BoxCliError("auth_required", "no login", retryable=False)
        box_contract.output_envelope(error=err)
        doc = json.loads(capsys.readouterr().out)
        assert doc["ok"] is False
        assert doc["error"]["code"] == "auth_required"
        assert doc["error"]["retryable"] is False

    def test_envelope_emitted_only_once(self, capsys):
        box_contract.output_envelope(result={})
        box_contract.output_envelope(result={"second": True})
        out = capsys.readouterr().out
        assert out.count("\n") == 1
        assert "second" not in out

    def test_every_error_code_has_exit_code(self):
        for code, code_num in box_contract.EXIT_CODES.items():
            assert isinstance(code_num, int) and code_num >= 1
        assert box_contract.EXIT_CODES["invalid_input"] == 2
        assert box_contract.EXIT_CODES["auth_required"] == 4
        assert box_contract.EXIT_CODES["cancelled"] == 130

    def test_app_version_is_bare_semver(self):
        assert re.fullmatch(r"\d+\.\d+\.\d+", box_contract.APP_VERSION)


class TestStats:
    @pytest.fixture()
    def data_root(self, tmp_path, monkeypatch):
        import config

        monkeypatch.setattr(config, "SAVE_DATA_PATH", str(tmp_path))
        yield tmp_path
        monkeypatch.setattr(config, "SAVE_DATA_PATH", "")

    def _write(self, root, rel, content):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_jsonl_increment(self, data_root):
        self._write(data_root, "xhs/jsonl/search_contents_2026-09-19.jsonl", '{"a":1}\n{"b":2}\n')
        snap = box_contract.snapshot_output_files("xhs", "search")
        assert len(snap) == 1

        self._write(data_root, "xhs/jsonl/search_contents_2026-09-19.jsonl",
                    '{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n')
        result = box_contract.collect_new_files("xhs", "search", snap)
        assert result == [{"path": os.path.abspath(
            str(data_root / "xhs/jsonl/search_contents_2026-09-19.jsonl")), "items_added": 2}]

    def test_new_file_counted_in_full(self, data_root):
        snap = box_contract.snapshot_output_files("xhs", "search")
        assert snap == {}
        self._write(data_root, "xhs/csv/search_contents_2026-09-19.csv",
                    "title,desc\nn1,x\nn2,y\n")
        result = box_contract.collect_new_files("xhs", "search", snap)
        assert result[0]["items_added"] == 2  # csv 计数扣除表头

    def test_other_crawler_types_ignored(self, data_root):
        self._write(data_root, "xhs/jsonl/detail_contents_2026-09-19.jsonl", '{"a":1}\n')
        snap = box_contract.snapshot_output_files("xhs", "search")
        assert snap == {}


class TestLoginProfiles:
    def test_profile_paths_cover_both_modes(self):
        paths = box_contract.login_profile_paths("xhs")
        assert len(paths) == 2
        assert any(p.endswith("xhs_user_data_dir") for p in paths)
        assert any(p.endswith("cdp_xhs_user_data_dir") for p in paths)

    def test_has_login_profile_requires_default_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(box_contract, "get_writable_root", lambda: str(tmp_path))
        plain, cdp = box_contract.login_profile_paths("xhs")
        os.makedirs(os.path.join(cdp, "Default"))
        assert box_contract.has_login_profile("xhs") is True
        assert box_contract.has_login_profile("dy") is False


# ---------------------------------------------------------------------------
# 黑盒：plugin-box Catalog 准入样例
# ---------------------------------------------------------------------------

class TestBlackboxContract:
    def test_version_contract_exact_semver(self):
        proc = run_cli("--version")
        assert proc.returncode == 0
        assert proc.stdout.strip() == box_contract.APP_VERSION
        assert proc.stderr == ""

    def test_doctor_json_is_parseable_envelope(self):
        proc = run_cli("doctor", "--json")
        assert proc.returncode == 0
        doc = json.loads(proc.stdout)
        assert doc["contract_version"] == "1"
        assert doc["ok"] is True
        result = doc["result"]
        assert set(result["chrome"].keys()) == {"found", "path"}
        assert set(result["platforms"].keys()) == set(box_contract.SUPPORTED_PLATFORMS)

    def test_invalid_param_returns_invalid_input_envelope(self):
        proc = run_cli("--platform", "foo", "--json")
        assert proc.returncode == box_contract.EXIT_CODES["invalid_input"]
        doc = json.loads(proc.stdout)
        assert doc["ok"] is False
        assert doc["error"]["code"] == "invalid_input"

    def test_json_crawl_without_login_profile_is_auth_required(self):
        # 源码模式可写根 = cwd：在空目录里跑子进程，隔离真实 browser_data
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(
                "--platform", "xhs", "--type", "search", "--keywords", "t", "--json",
                cwd=tmp,
            )
        assert proc.returncode == box_contract.EXIT_CODES["auth_required"]
        doc = json.loads(proc.stdout)
        assert doc["error"]["code"] == "auth_required"
        assert "login --platform xhs" in doc["error"]["message"]
