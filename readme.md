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
- Keeps west-managed source checkouts under `.west-workspace/`

## Usage

### Local build environment

> [!important]
> On Windows, it is recommended that the workspace be located on WSL-native location (outside of `/mnt/c/`). Syncing the directory between Windows and WSL / container will result in significantly slower builds.

On WSL, you can edit files directly in the WSL workspace and run `./just.sh init`, `./just.sh update`, `./just.sh list`, `./just.sh build`, `./just.sh test`, and `./just.sh flash` from WSL. Build-related commands execute `just` and the ZMK toolchain inside Docker using `.devcontainer/Dockerfile`, while generated files remain owned by your WSL user. West-managed source checkouts are placed under `.west-workspace/` instead of the repository root. Firmware files are written to `firmware/<config-folder>/`. Flashing stays on the WSL host so it can call PowerShell and access the UF2 drive.

Builds use `ccache` inside the container. The cache is stored at `.cache/ccache` on the WSL filesystem and is ignored by Git. You can inspect it with `./just.sh ccache-stats` and clear it with `./just.sh clean-ccache`. The default cache limit is 5 GiB; override it with `ZMK_WORKSPACE_CCACHE_MAXSIZE=10G ./just.sh build all`.

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
   This writes `keymap-svg/<name>.svg` from the ZMK `zmk,physical-layout` node and `config/<name>.keymap`.

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

## 日本語メモ

このリポジトリは、WSL 上でファイルを編集し、ビルドに必要な ZMK / Zephyr のツールチェーンだけを Docker コンテナ内で実行するためのワークスペースです。VS Code の Dev Container 内でファイルを作ると、WSL 側から編集や削除がしづらくなることがあります。そのため、普段の編集対象は WSL のファイルとして保持し、`./just.sh` が必要なときだけコンテナを起動します。

基本的には次の流れで使います。

```sh
./just.sh init config/zmk-config-SparAkashaAnanta
./just.sh build all
./just.sh draw-keymap
```

`init` で取得される ZMK / Zephyr / modules などの west 管理ファイルは、リポジトリ直下ではなく `.west-workspace/` に作られます。作業用リポジトリの直下が west のクローンで散らからないようにするためです。

ビルド結果の UF2 ファイルは config ごとに分けて、`firmware/<config-folder>/` に出力されます。たとえば `config/zmk-config-SparAkashaAnanta` を使っている場合は、`firmware/zmk-config-SparAkashaAnanta/` に生成されます。

ビルド時はコンテナ内で `ccache` を使います。キャッシュ本体は WSL 側の `.cache/ccache` に保存され、Git には含めません。状態を見るには `./just.sh ccache-stats`、キャッシュを消すには `./just.sh clean-ccache` を使います。既定の上限は 5 GiB で、必要なら `ZMK_WORKSPACE_CCACHE_MAXSIZE=10G ./just.sh build all` のように増やせます。

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
