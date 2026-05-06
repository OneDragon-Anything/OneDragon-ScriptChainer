import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
)
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from script_chainer.context.script_chainer_context import ScriptChainerContext

ProgressCallback = Callable[[float, str], None]

APP_EXE_NAMES = (
    'OneDragon ScriptChainer.exe',
    'OneDragon ScriptChainer Runner.exe',
)
RELEASE_ZIP_PREFIX = 'OneDragon-ScriptChainer'
UPDATE_DIR_NAME = 'github_update'
RUNTIME_DIR_NAME = '.runtime'


class GithubUpdateService:
    """下载 GitHub Release，并在进程退出后替换发布版文件。"""

    def __init__(self, ctx: 'ScriptChainerContext'):
        self.ctx = ctx

    def download_and_restart(
        self,
        target_tag: str | None = None,
        progress_callback: ProgressCallback | None = None,
        progress_signal: dict[str, str | None] | None = None,
    ) -> tuple[bool, str]:
        if not os_utils.run_in_exe():
            return False, gt('当前不是发布版，无法自动更新')

        work_dir = Path(os_utils.get_work_dir())
        update_dir = work_dir / '.temp' / UPDATE_DIR_NAME
        stage_dir = update_dir / 'stage'

        try:
            if update_dir.exists():
                shutil.rmtree(update_dir)
            stage_dir.mkdir(parents=True, exist_ok=True)

            if progress_callback is not None:
                progress_callback(0, gt('正在获取 GitHub 更新版本'))
            latest_tag = target_tag or self.get_latest_tag()
            downloader_param = self._get_downloader_param(latest_tag, update_dir)
            release_zip_name = downloader_param.save_file_name
            zip_path = update_dir / release_zip_name
            downloader = CommonDownloader(downloader_param)
            proxy = self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None
            ghproxy_url = self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None
            if not downloader.download(
                proxy_url=proxy,
                ghproxy_url=ghproxy_url,
                skip_if_existed=False,
                progress_signal=progress_signal,
                progress_callback=progress_callback,
            ):
                if progress_signal is not None and progress_signal.get('signal') == 'cancel':
                    return False, gt('下载已取消')
                return False, gt('下载 GitHub 更新失败')

            if progress_signal is not None and progress_signal.get('signal') == 'cancel':
                return False, gt('下载已取消')

            if progress_callback is not None:
                progress_callback(1, gt('正在解压更新包'))
            self._extract_release(zip_path, stage_dir)

            update_items = self._get_update_items(stage_dir)
            if not update_items:
                return False, gt('更新包中没有可替换文件')

            script_path = self._write_apply_script(work_dir, update_dir, update_items)
            self._start_apply_script(script_path, work_dir)
            return True, gt('更新包已下载完成，程序将重启并替换文件')
        except Exception as e:
            log.error('准备 GitHub 更新失败', exc_info=True)
            return False, f"{gt('准备 GitHub 更新失败')}: {e}"

    def get_latest_tags(self) -> tuple[str, str]:
        stable_tag = self.get_latest_tag()
        try:
            beta_tag = self.get_latest_beta_tag()
        except Exception:
            log.error('获取 GitHub 最新测试版失败', exc_info=True)
            beta_tag = ''
        return stable_tag, beta_tag

    def get_latest_tag(self) -> str:
        repo_path = self._get_github_repo_path()
        release_url = f'https://api.github.com/repos/{repo_path}/releases/latest'
        with self._open_request(release_url, headers={'User-Agent': 'OneDragon-ScriptChainer'}) as response:
            release = json.loads(response.read().decode('utf-8'))

        tag = str(release.get('tag_name', '')).strip()
        if not tag:
            raise RuntimeError(f'无法解析最新版本: {release_url}')
        return tag

    def get_latest_beta_tag(self) -> str:
        repo_path = self._get_github_repo_path()
        releases_url = f'https://api.github.com/repos/{repo_path}/releases?per_page=30'
        with self._open_request(releases_url, headers={'User-Agent': 'OneDragon-ScriptChainer'}) as response:
            releases = json.loads(response.read().decode('utf-8'))

        for release in releases:
            if release.get('draft'):
                continue
            if release.get('prerelease'):
                tag = str(release.get('tag_name', '')).strip()
                if tag:
                    return tag

        return ''

    def _get_github_repo_path(self) -> str:
        parsed = urllib.parse.urlparse(self.ctx.project_config.github_homepage)
        repo_path = parsed.path.strip('/')
        if repo_path.endswith('.git'):
            repo_path = repo_path[:-4]
        if repo_path.count('/') < 1:
            raise RuntimeError(f'无法解析 GitHub 仓库地址: {self.ctx.project_config.github_homepage}')
        return repo_path

    def _open_request(
        self,
        url: str,
        method: str = 'GET',
        headers: dict[str, str] | None = None,
    ):
        request = urllib.request.Request(url, method=method, headers=headers or {})
        return self._build_opener().open(request, timeout=15)

    def _build_opener(self):
        proxy = self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None
        proxy_handler = (
            urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            if proxy is not None else urllib.request.ProxyHandler({})
        )
        return urllib.request.build_opener(proxy_handler)

    def _get_downloader_param(self, latest_tag: str, update_dir: Path) -> CommonDownloaderParam:
        release_zip_name = f'{RELEASE_ZIP_PREFIX}-{latest_tag}.zip'
        download_url = (
            f'{self.ctx.project_config.github_homepage}'
            f'/releases/download/{latest_tag}/{release_zip_name}'
        )

        return CommonDownloaderParam(
            save_file_path=str(update_dir),
            save_file_name=release_zip_name,
            github_release_download_url=download_url,
        )

    def _extract_release(self, zip_path: Path, stage_dir: Path) -> None:
        stage_root = stage_dir.resolve()
        with zipfile.ZipFile(zip_path) as zip_file:
            root_dir = self._detect_root_dir(zip_file)
            for info in zip_file.infolist():
                if info.is_dir():
                    continue

                parts = PurePosixPath(info.filename.replace('\\', '/')).parts
                if root_dir is not None and parts and parts[0] == root_dir:
                    parts = parts[1:]
                if not parts or '..' in parts:
                    continue
                if not self._should_extract(parts):
                    continue

                target_path = stage_dir.joinpath(*parts)
                if not self._is_relative_to(target_path.resolve(), stage_root):
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zip_file.open(info) as source, target_path.open('wb') as target:
                    shutil.copyfileobj(source, target)

    def _detect_root_dir(self, zip_file: zipfile.ZipFile) -> str | None:
        file_parts = [
            PurePosixPath(info.filename.replace('\\', '/')).parts
            for info in zip_file.infolist()
            if not info.is_dir()
        ]
        if not file_parts:
            return None

        first_parts = [parts[0] for parts in file_parts if len(parts) > 1]
        if len(first_parts) != len(file_parts):
            return None

        root_dir = first_parts[0]
        return root_dir if all(part == root_dir for part in first_parts) else None

    def _should_extract(self, parts: tuple[str, ...]) -> bool:
        top_name = parts[0]
        if top_name == RUNTIME_DIR_NAME:
            return True
        return len(parts) == 1 and top_name.lower().endswith('.exe')

    def _get_update_items(self, stage_dir: Path) -> list[Path]:
        items: list[Path] = []
        for name in (*APP_EXE_NAMES, RUNTIME_DIR_NAME):
            item_path = stage_dir / name
            if item_path.exists():
                items.append(item_path)

        known_names = {item.name for item in items}
        for item_path in stage_dir.glob('*.exe'):
            if item_path.name not in known_names:
                items.append(item_path)
        return items

    def _write_apply_script(
        self,
        work_dir: Path,
        update_dir: Path,
        update_items: list[Path],
    ) -> Path:
        lines = [
            "$ErrorActionPreference = 'Stop'",
            f'$ProcessIdToWait = {os.getpid()}',
            f'$CurrentExe = {self._ps_quote(sys.executable)}',
            f'$WorkDir = {self._ps_quote(str(work_dir))}',
            'Start-Sleep -Milliseconds 500',
            'try { Wait-Process -Id $ProcessIdToWait -Timeout 30 -ErrorAction SilentlyContinue } catch {}',
        ]

        for item_path in update_items:
            target_path = work_dir / item_path.name
            backup_path = work_dir / f'{item_path.name}.bak'
            lines.extend([
                f'$Source = {self._ps_quote(str(item_path))}',
                f'$Target = {self._ps_quote(str(target_path))}',
                f'$Backup = {self._ps_quote(str(backup_path))}',
                'if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force }',
                'if (Test-Path -LiteralPath $Target) { Move-Item -LiteralPath $Target -Destination $Backup -Force }',
                'try {',
                '    Move-Item -LiteralPath $Source -Destination $Target -Force',
                '    if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force }',
                '} catch {',
                '    if (Test-Path -LiteralPath $Backup) {',
                '        if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }',
                '        Move-Item -LiteralPath $Backup -Destination $Target -Force',
                '    }',
                '    throw',
                '}',
            ])

        lines.extend([
            'Start-Process -FilePath $CurrentExe -WorkingDirectory $WorkDir',
            f'Remove-Item -LiteralPath {self._ps_quote(str(update_dir))} -Recurse -Force',
        ])

        script_path = update_dir / 'apply_update.ps1'
        script_path.write_text('\n'.join(lines), encoding='utf-8')
        return script_path

    def _start_apply_script(self, script_path: Path, work_dir: Path) -> None:
        subprocess.Popen(
            [
                'powershell',
                '-NoProfile',
                '-ExecutionPolicy',
                'Bypass',
                '-File',
                str(script_path),
            ],
            cwd=str(work_dir),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _ps_quote(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
