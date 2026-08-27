# zmk-workspace

This repository is a workspace for building ZMK firmware, based on [urob's zmk-config](https://github.com/urob/zmk-config).

This workspace also refers to [kot149/zmk-workspace](https://github.com/kot149/zmk-workspace). Thanks to the author for sharing the original workflow and repository structure.

Difference from urob's zmk-config:
- zmk-config can also be in subdirectory of `config/` (while `config/` is still supported). This enables you to have multiple zmk-configs.
- Supports extra modules for zmk-config and tests
- Dev Container support
- keymap-drawer support
- Physical layout SVG preview support
- Tab completion for `just build` and `just flash` with fzf
- `just flash` is added for UF2 loader (Only works on Winodws(WSL) or macOS with Nix)
- Groups west checkouts, build trees, and logs under `.zmk-workspace/profiles/`

## Usage

### Local build environment

> [!important]
> On Windows, it is recommended that the workspace be located on WSL-native location (outside of `/mnt/c/`). Syncing the directory between Windows and WSL / container will result in significantly slower builds.

On WSL, you can edit files directly in the WSL workspace and run `./just.sh init`, `./just.sh update`, `./just.sh list`, `./just.sh build`, `./just.sh test`, and `./just.sh flash` from WSL. Build-related commands execute `just` and the ZMK toolchain inside Docker using `.devcontainer/Dockerfile`, while generated files remain owned by your WSL user. Build trees, west checkouts, and logs are grouped under `.zmk-workspace/profiles/<profile>/`. Firmware files are written to `firmware/<config-folder>/<branch>/`. Flashing stays on the WSL host so it can call PowerShell and access the UF2 drive.

Builds use `ccache` inside the container. The shared cache is stored at `.zmk-workspace/cache/ccache` on the WSL filesystem and is ignored by Git. You can inspect it with `./just.sh ccache-stats` and clear it with `./just.sh clean-ccache`. The default cache limit is 5 GiB; override it with `ZMK_WORKSPACE_CCACHE_MAXSIZE=10G ./just.sh build all`.

Use profiles to isolate experiments without creating `.build-*` and `.west-workspace-*` directories in the repository root:

```sh
./just.sh profile polaris-dya-v2
./just.sh init config/zmk-config-GeaconPolaris
./just.sh build all
./just.sh paths
```

The selected profile remains active. Use `./just.sh --profile <name> <command>` for a one-off command, and `./just.sh profiles` to list profiles. During `init`, the wrapper records the config repository name (from its `origin` remote) and branch in the profile metadata. Firmware therefore keeps the canonical `firmware/<repository>/<branch>/` path even if the config worktree is moved later. `ZMK_CONFIG_NAME` and `ZMK_CONFIG_BRANCH` override the saved metadata when an explicit destination is needed; non-Git configs fall back to the profile name instead of `nogit`. Existing root-level build directories can be reviewed with `./just.sh organize --dry-run` and moved into a timestamped archive with `./just.sh organize --apply`; no data is deleted.

Incremental builds reuse the existing Ninja build tree and only run CMake when one of its dependencies changes. To build several matching targets as quickly as possible, use the auto-tuned parallel recipe:

```sh
./just.sh build-fast all
```

It chooses target-level and compiler-level parallelism from the available CPU and memory. Override either level when benchmarking or on a constrained machine:

```sh
ZMK_TARGET_JOBS=3 CMAKE_BUILD_PARALLEL_LEVEL=4 ./just.sh build-fast all
```

1. Clone this repo
1. See [VSCode Docs](https://code.visualstudio.com/docs/devcontainers/containers) for Dev Conainer usage. Or, see [urob's zmk-config README](https://github.com/urob/zmk-config#local-build-environment) for Nix and direnv setup
2. git clone your zmk-config into `config`
   ```sh
   cd config
   git clone https://github.com/your-username/zmk-config-your-keyboard
   cd ..
   ```
4. Init and select the target config
   ```sh
   ./just.sh init config/zmk-config-your-keyboard
   ```
   Or if you prefer to treat zmk-workspace as the root of your zmk-config,
   ```sh
   ./just.sh init config
   ```
   You can omit the config name to use fzf to select the config.
5. Build
   ```sh
   ./just.sh build [target]
   ```
6. Flash
   ```sh
   ./just.sh flash [target]
   ```
   or you can specify `-r` to build before flashing
   ```sh
   ./just.sh flash [target] -r
   ```

   On Windows/WSL, boards that include a 1200-baud CDC ACM bootloader trigger can also be flashed and logged in one loop:
   ```sh
   ./just.sh flash-log [target-or-uf2] COM12 --build --seconds 90
   ```
   To inspect visible COM ports and mounted UF2 drives without flashing:
   ```sh
   ./just.sh diagnose-ports COM12
   ```
   See [`docs/zmk-flash-log-loop.md`](docs/zmk-flash-log-loop.md) for the reusable protocol.

7. Draw keymap
   ```sh
   ./just.sh draw-keymap
   ```
   or draw a specific `config/*.keymap` basename
   ```sh
   ./just.sh draw-keymap SAA
   ```
   This also regenerates `config/<name>.json` from the ZMK physical layout before drawing.

8. Draw physical-layout-based keymap preview
   ```sh
   ./just.sh draw-physical-layout
   ```
   or draw a specific `config/*.keymap` basename
   ```sh
   ./just.sh draw-physical-layout SAA
   ```
   This writes `keymap-svg/<name>.svg` from the ZMK `zmk,physical-layout` node and `config/<name>.keymap`. ZMK `combos` are drawn as overlays connecting their `key-positions`.

9. Use the reusable GitHub Actions workflow

   ZMK config repositories can call the workflow in this repository without copying the generator script into the firmware repository.

   ```yaml
   jobs:
     draw-keymap-svg:
       uses: te9no/zmk-workspace/.github/workflows/draw-keymap-svg.yml@main
       permissions:
         contents: write
       with:
         commit_message: "[Draw keymap-svg] ${{ github.event.head_commit.message || 'manual run' }}"
         amend_commit: false
         keymap_patterns: "config/*.keymap"
         output_folder: "keymap-svg"
         destination: "both"
         artifact_name: "keymap-svg"
   ```

   The workflow checks out this repository separately and runs `scripts/generate_physical_layout_svg.py` from there.

10. Use the reusable firmware build workflow

   ZMK config repositories can also call the firmware build workflow in this repository without copying the matrix composer script or the full build job into each config repository.

   ```yaml
   name: Build ZMK firmware

   on:
     workflow_dispatch:
       inputs:
         target:
           description: "Regex matched against artifact-name, board, shield, and snippet. Use 'all' for every target."
           required: false
           default: "all"
         commit_firmware:
           description: "Commit built firmware files back to this branch."
           required: false
           default: true
           type: boolean
     push:
       paths:
         - "config/**"
         - "boards/**"
         - "snippets/**"
         - "build.yaml"
         - "zephyr/module.yml"
         - ".github/workflows/build.yml"

   jobs:
     build:
       uses: te9no/zmk-workspace/.github/workflows/build-zmk-firmware.yml@main
       permissions:
         contents: write
         actions: read
       with:
         target: ${{ inputs.target || 'all' }}
         commit_firmware: ${{ inputs.commit_firmware != false }}
         build_yaml: "build.yaml"
         firmware_folder: "firmware"
         update_build_health: true
         badge_folder: "badges/build-health"
         max_parallel: 4
   ```

   The reusable workflow reads `build.yaml`, composes a matrix, prepares a west workspace, restores west and ccache caches, builds each target, uploads each successful firmware artifact, and optionally commits merged firmware files under `firmware/<safe-repository-name>/<safe-branch-name>/`.

   When `update_build_health` is enabled, the workflow also writes build health files under `badges/build-health/<safe-repository-name>/<safe-branch-name>/`:

   - `build-health.svg`
   - `build-health.json`
   - `shields.json`

   A README badge can reference the committed SVG:

   ```md
   ![build health](badges/build-health/zmk-config-your-keyboard/main/build-health.svg)
   ```

11. Use the reusable build health badge workflow directly

   If you already have a custom build workflow, call the badge workflow from a final job:

   ```yaml
   jobs:
     build:
       # your build job here

     build-health:
       needs: build
       if: always()
       uses: te9no/zmk-workspace/.github/workflows/update-build-health-badge.yml@main
       permissions:
         contents: write
       with:
         status: ${{ needs.build.result }}
         target: "all"
         badge_folder: "badges/build-health"
   ```

## 日本語メモ

このリポジトリは、WSL 上でファイルを編集し、ビルドに必要な ZMK / Zephyr のツールチェーンだけを Docker コンテナ内で実行するためのワークスペースです。VS Code の Dev Container 内でファイルを作ると、WSL 側から編集や削除がしづらくなることがあります。そのため、普段の編集対象は WSL のファイルとして保持し、`./just.sh` が必要なときだけコンテナを起動します。

基本的には次の流れで使います。

```sh
./just.sh init config/zmk-config-SparAkashaAnanta
./just.sh build all
./just.sh draw-keymap
```

USB CDC ACM の 1200 baud bootloader trigger が入ったファームウェアでは、ビルド、UF2 書き込み、シリアルログ取得をまとめて実行できます。

```sh
./just.sh flash-log MY_KEYBOARD_RIGHT COM12 --build --seconds 90
```

書き込み前に Windows 側で見えている COM ポートと UF2 ドライブだけ確認する場合です。

```sh
./just.sh diagnose-ports COM12
```

詳細は `docs/zmk-flash-log-loop.md` にまとめています。

`init` で取得される ZMK / Zephyr / modules、ビルドツリー、並列ビルドのログは、`.zmk-workspace/profiles/<プロファイル名>/` の下へまとめて作られます。実験ごとに `.build-*` や `.west-workspace-*` がリポジトリ直下へ増えない構成です。

たとえば Polaris の DYA Studio V2 検証環境を分離する場合は、次のようにプロファイルを選択してから初期化します。選択したプロファイルは次回以降も維持されます。

```sh
./just.sh profile polaris-dya-v2
./just.sh init config/zmk-config-GeaconPolaris
./just.sh build all
./just.sh paths
```

一度だけ別プロファイルを使う場合は `./just.sh --profile <名前> <コマンド>`、一覧は `./just.sh profiles` を使用します。`init` 時にはconfigリポジトリの`origin`名とブランチをプロファイルのmetadataへ保存するため、worktreeを移動してもfirmwareの保存先は正規の `firmware/<repository>/<branch>/` のままです。保存先を明示する場合は `ZMK_CONFIG_NAME` / `ZMK_CONFIG_BRANCH` がmetadataより優先され、Git管理外のconfigでは`nogit`ではなくプロファイル名を使用します。現在ルート直下にある旧 `.build-*` / `.west-workspace-*` は、`./just.sh organize --dry-run` で移動内容を確認し、`./just.sh organize --apply` で `.zmk-workspace/archive/<日時>/` へ退避できます。この操作ではファイルを削除しません。

ビルド結果の UF2 ファイルは config とブランチごとに分けて、`firmware/<config-folder>/<branch>/` に出力されます。たとえば `config/zmk-config-SparAkashaAnanta` の `feat/add-iqs-module-and-led-support` ブランチを使っている場合は、`firmware/zmk-config-SparAkashaAnanta/feat-add-iqs-module-and-led-support/` に生成されます。

ビルド時はコンテナ内で `ccache` を使います。全プロファイルで共有するキャッシュは WSL 側の `.zmk-workspace/cache/ccache` に保存され、Git には含めません。状態を見るには `./just.sh ccache-stats`、キャッシュを消すには `./just.sh clean-ccache` を使います。既定の上限は 5 GiB で、必要なら `ZMK_WORKSPACE_CCACHE_MAXSIZE=10G ./just.sh build all` のように増やせます。

通常の `./just.sh build <target>` は既存の Ninja ビルドツリーを再利用し、変更された依存関係だけを処理します。複数ターゲットをまとめて最速でビルドする場合は、CPU数とメモリ量から並列度を自動調整する次のコマンドを使えます。

```sh
./just.sh build-fast all
```

並列度を固定したい場合は、`ZMK_TARGET_JOBS=3 CMAKE_BUILD_PARALLEL_LEVEL=4 ./just.sh build-fast all` のように指定します。

`config/zmk-config-SparAkashaAnanta` は、この workspace とは別の Git リポジトリとして扱えます。VS Code で親 workspace と config リポジトリの両方を認識させたい場合は、`config/zmk-config-SparAkashaAnanta` フォルダ自体にも `.git` がある状態にして、VS Code の Source Control で複数リポジトリとして表示させます。

現在のローカル内容で GitHub 側を上書きしたい場合は、config リポジトリを先に push してから、親 workspace を push します。

```sh
cd /home/owner/zmk-workspace2/zmk-workspace/config/zmk-config-SparAkashaAnanta
git push --force-with-lease origin master

cd /home/owner/zmk-workspace2/zmk-workspace
git push --force-with-lease te9no main
```

`--force-with-lease` は通常の force push より少し安全で、最後に取得した remote からさらに更新されている場合は上書きを止めます。完全に上書きしたい場合だけ `--force` を使ってください。

## Tab completion

Enable completion in the current Bash session:

```sh
source ./_just_completion.bash
```

Then use `Tab` after `./just.sh`, for example:

```sh
./just.sh <Tab>
./just.sh build <Tab>
./just.sh init <Tab>
```

To enable it automatically in Bash, add this to `~/.bashrc`:

```sh
source /home/owner/zmk-workspace2/zmk-workspace/_just_completion.bash
```

The completion works with `./just.sh` on WSL. If `fzf` is installed on the host, target/config selection uses an interactive picker; otherwise it falls back to normal Bash completion candidates.
