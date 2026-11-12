# ContactGlove ROS2 SDK V2 の開発

[English](DEVELOPMENT.md) | 日本語

SDKソースのビルド、テスト、配布物の生成手順です。
配布物の導入・操作・APIは[Webドキュメント](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2)を参照してください。

## パッケージ構成

```
src/
├── contact_glove_msgs/  # メッセージ定義
└── contact_glove/       # ドライバーノード・ビジュアライザーノード
vendor/contactglove-sdk-v2/  # 固定コミットのC++ SDK submodule
scripts/
├── install_contactglove_sdk_deb.sh  # 実行環境に合う C++ SDK deb をインストール
├── package_ros2.sh                  # ブリッジDEBとメッセージ単独DEBを含む配布ZIPを生成
├── package_ros2_msgs.sh             # contact_glove_msgsだけをビルドしてDEBを生成
└── mock_server/
    └── server.py          # 実機なしで動作確認できるモックサーバー
packaging/
├── README.md              # 配布パッケージ向け最小導入手順（英語）
└── README_JA.md           # 配布パッケージ向け最小導入手順（日本語）
```

`contact_glove_msgs` が提供するメッセージ型・`contact_glove` が提供するノードの一覧は
[APIリファレンス](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/api) を参照してください。

---

## ビルド・実行

### 動作確認済み環境

- Ubuntu 24.04 (Noble) + ROS2 Jazzy
- Ubuntu 22.04 (Jammy) + ROS2 Humble

### サポートバージョンについて

本リポジトリは **現行 LTS ディストリビューションのみ**をサポート対象とします。現時点でのサポート対象は上記の Jazzy / Humble の 2 系統のみで、対応する `.deb` もこの 2 種類のみ提供します。

- サポート対象は各ディストリビューションの EOL（End of Life）に合わせて見直します。目安として、**EOL 後おおむね 6 ヶ月でサポートを打ち切り**、以後の新機能・修正は対象外とします。
  - ROS2 Humble: EOL 予定 2027-05
  - ROS2 Jazzy: EOL 予定 2029-05
- **ROS1（Noetic を含む）はサポート対象外**です。
- 上記以外の EOL 済みディストリビューション（例: Ubuntu 20.04 / ROS2 Foxy・Galactic など）についても同様にサポート対象外です。

### メッセージ単独DEBのビルド

`contactglove-ros2-msgs` だけを生成する場合は、DivingStationやContactGlove C++/C/Rust SDK V2を導入せずにビルドできます。
対象はUbuntu 22.04 / ROS2 Humble / amd64と、Ubuntu 24.04 / ROS2 Jazzy / amd64です。
対象OS・CPUアーキテクチャの環境で、このリポジトリのルートから実行してください。

```bash
# Ubuntu 22.04 / ROS2 Humble
sudo apt update
sudo apt install build-essential cmake dpkg-dev python3-colcon-common-extensions \
  ros-humble-ament-cmake-auto ros-humble-rosidl-default-generators \
  ros-humble-geometry-msgs ros-humble-std-msgs
source /opt/ros/humble/setup.bash
export PACKAGE_BUILD_ID=12345.1  # 配布ごとに異なるIDを使う
bash scripts/package_ros2_msgs.sh humble jammy

# Ubuntu 24.04 / ROS2 Jazzyでは、依存パッケージのhumbleをjazzyに置き換える
# source /opt/ros/jazzy/setup.bash
# bash scripts/package_ros2_msgs.sh jazzy noble
```

生成先は `dist/contactglove-ros2-msgs_<version>-1<codename>+ros2.<build-id>_amd64.deb` です。
スクリプトは一時ディレクトリで `contact_glove_msgs` をビルドします。
`scripts/verify_ros2_msgs_deb_install.sh` はDEBのインストールと生成済みインターフェースを検証します。
パッケージをインストールするため、検証には使い捨てのROSコンテナを使用してください。

以下は、ブリッジを含むSDK全体をビルドするための手順です。

### 依存ライブラリのインストール

#### システムパッケージ

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  file \
  git \
  python3-colcon-common-extensions \
  ros-jazzy-rclcpp \
  ros-jazzy-rclpy \
  ros-jazzy-geometry-msgs \
  ros-jazzy-std-msgs \
  ros-jazzy-sensor-msgs \
  ros-jazzy-visualization-msgs \
  ros-jazzy-tf2-ros \
  ros-jazzy-rviz2 \
  ros-jazzy-xacro \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-ament-cmake-auto \
  ros-jazzy-ament-lint-auto \
  ros-jazzy-ament-lint-common \
  ros-jazzy-ament-cmake-gtest \
  ros-jazzy-rosidl-default-generators \
  ros-jazzy-rosidl-default-runtime
```

> `ros-jazzy-desktop` を導入済みであれば、`rclcpp` から `rviz2` までの実行時依存パッケージは個別インストール不要ですが、ビルド・テスト用の `ament-*` / `rosidl-*` パッケージは上記のとおりインストールしてください。
> `ros-jazzy-xacro` / `ros-jazzy-robot-state-publisher` は `contact_glove_with_urdf.launch.xml`（URDF + `robot_state_publisher` によるロボット可視化）を使う場合にのみ必要です。それ以外の機能では不要ですが、`colcon test` は xacro が無いと urdf の joint 名検証テスト（`check_urdf_joint_names_*`）をスキップします。
> ROS2 Humble を使用する場合は、上記の `ros-jazzy-*` を `ros-humble-*` に読み替えてください。

#### Python パッケージ（モックサーバーを使う場合のみ）

```bash
sudo apt-get install python3-venv
python3 -m venv /tmp/contactglove-mock-venv
/tmp/contactglove-mock-venv/bin/python -m pip install python-osc
```

#### ContactGlove C++/C/Rust SDK V2 のランタイム

このROS2パッケージはC++ SDKの `ContactGloveSDKv2::ContactGloveSDKv2` CMake targetにリンクします。
C++ SDK 1.0.0を固定submoduleからビルドし、DEBを作業ディレクトリに展開して参照できます。
CMakeの要求版も1.0.0です。
`vendor/COLCON_IGNORE` により、通常の `colcon build` はSDK自体を探索しません。
DivingStation v2以降を使用してください。

### リポジトリのセットアップ

```bash
git clone --recurse-submodules https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2ROS2.git
cd ContactGloveSDKv2ROS2
```

C++ SDKは公開リポジトリのv1.0.0 (`8223da430eed7e5e41f601b59732a260d6ce1cd1`) に固定しています。
既存のcloneでは `git submodule sync --recursive` の後に
`git submodule update --init --recursive` を実行してください。
msgsのみのビルドにはsubmoduleは不要です。C++ SDKのビルドは固定された
oscpackリビジョンをネットワークから取得します。

以下はJazzy/Nobleの例です。ビルドIDは配布ごとに一意な「正の整数.正の整数」を
先頭のゼロなしで使用してください。公式配布はGitHub Actionsのrun IDとattemptを使い、同じ
DEBバージョンで異なる内容を再配布しないでください。公式配布には必ず
GitHub Actionsの成果物を使い、手元の検証ビルドを配布しないでください。

```bash
export PACKAGE_BUILD_ID=12345.1
export SDK_BUILD_DIR="$PWD/../sdk-package"
bash scripts/build_cpp_sdk.sh noble "$SDK_BUILD_DIR"
mkdir -p ../sdk-prefix
dpkg-deb -x "$SDK_BUILD_DIR"/*.deb ../sdk-prefix
export ContactGloveSDKv2_DIR="$PWD/../sdk-prefix/usr/lib/x86_64-linux-gnu/cmake/ContactGloveSDKv2"
export LD_LIBRARY_PATH="$PWD/../sdk-prefix/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
```

ビルド時に `$SDK_BUILD_DIR/sdk-provenance.json` を生成し、
配布ZIPの `lib/sdk-provenance.json` に同梱します。

SDKの生成と配布には、ROS2とC++の追跡ファイルがそれぞれクリーンである
必要があります。未追跡ファイルやGitの無視対象も、インストール対象に混入する
可能性があるため拒否します。ROS2側のルートにある `build/`、`install/`、
`log/`、`dist/` と `scripts/__pycache__/` は生成物として除外します。
Gitの通常のソースアーカイブにはsubmodule内容が含まれません。
ソースをまとめる場合は、クリーンなcheckoutから
`python3 scripts/create_source_archive.py ../contactglove-source.tar.gz` を実行します。
このアーカイブは両ソースとファイルハッシュを含み、Git履歴は含みません。
同梱ハッシュは破損検出用で、ソースの真正性を証明する署名ではありません。

### ビルド

```bash
# Ubuntu 24.04 / ROS2 Jazzy の場合
source /opt/ros/jazzy/setup.bash

# Ubuntu 22.04 / ROS2 Humble の場合
# source /opt/ros/humble/setup.bash

colcon build --cmake-args -DContactGloveSDKv2_DIR="$ContactGloveSDKv2_DIR"
source install/setup.bash
```

> 以降のコマンドはすべて `source install/setup.bash` 済みの状態で実行してください。

### テスト

`contact_glove` には、メッセージ変換ロジック（`to_transform` / `wrist_frame_id` / ergonomics のインデックス割当など）の gtest 単体テストがあります。

```bash
colcon test
colcon test-result --verbose
```

固定C++ SDKからビルドしたランタイムに対して、250回の即時接続・切断と100回の即時SDK破棄も
30秒の上限付きで検証します。CI はさらに2つの実ROS2ノードで、承認待ち中の
再試行、送信元ポートの維持、不正OSC受信後の正常データ復旧、終了時のみの
Disconnect送信を確認します。実機を使わず、UDP通信先はループバックのみです。

```bash
timeout 45s python3 scripts/test_lan_retry.py \
  install/contact_glove/lib/contact_glove/contact_glove_node
```


`colcon test` ではcppcheck・lint_cmake・xmllintと、C/C++ソースを持つパッケージ向けのcpplintも実行します。
検査の設定は `src/contact_glove/CMakeLists.txt` と
`src/contact_glove_msgs/CMakeLists.txt` を参照してください。

GitHub Actions（`.github/workflows/ci.yml`）が Jazzy / Humble
の両方で `colcon build` + `colcon test` を実行します。

### CIでのROS導入方針

`scripts/setup_ros_ci.sh` はUbuntu 22.04/HumbleとUbuntu 24.04/Jazzyの
amd64ランナー用です。公式の[ROS APT sourceパッケージ](https://github.com/ros-infrastructure/ros-apt-source)を、
バージョンとUbuntuごとのSHA-256を固定して導入します。更新時はリリースの配布物を確認し、
バージョンと両方のチェックサムを更新したうえで、両環境のCIを実行してください。
従来の `ros-<distro>-desktop` を維持し、`ros-dev-tools` とビルドツールを導入します。
プロジェクト固有の依存パッケージは引き続きworkflowに明示します。

公式の[Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)・
[Jazzy](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)ガイドはOSの更新を推奨していますが、
このCIでは更新済みの使い捨てGitHub-hostedランナーを前提に、OS全体のAPT upgradeを省きます。
`apt-get install` による指定パッケージとその依存関係の更新は許容するため、環境全体の
バージョンを固定する仕組みではありません。パッケージ削除が必要な導入は拒否します。
APT一覧の一部取得失敗やダウンロード失敗はエラーとし、古い一覧で続行したり、
OS全体のupgradeで回復を試みたりしません。古いOSやself-hosted環境向けの汎用インストーラーではなく、
Humbleの公式ガイドにある初期Jammyのsystemd/udev問題にも注意が必要です。

`ros-tooling/setup-ros@v0.7` にはupgradeを無効にする入力がなく、Jammyではupgradeを実行します。
Nobleではもともとこの処理を省いています。小さな導入スクリプトに置き換えることで、
既存のビルド・試験・パッケージ作成・新規コンテナでの利用者側検証を変えずに、導入方針を確認できます。
`python3 -m unittest discover -s scripts -p 'test_setup_ros_ci.py' -v` はコマンドを記録する
回帰テストで、root権限もネットワークも使いません。実際の導入はHumble/JazzyのCIで検証します。

### 実機なし（モックサーバー）での動作確認

`scripts/mock_server/server.py` は実機の DivingStation の代わりとなるモックサーバーです。
引数なしで左右の手の合成データを生成するため、実機なしで動作を確認できます。
待ち受けは `127.0.0.1:25791`（UDP）のみです。ROS2ノードも同じホスト・ネットワーク名前空間で実行してください。
仮想環境の準備とテスト方法は[モックサーバーの説明](scripts/mock_server/README_JA.md)を参照してください。

```bash
# ターミナル 1: モックサーバーを起動
/tmp/contactglove-mock-venv/bin/python scripts/mock_server/server.py

# ターミナル 2: ROS2 ノードを起動
source install/setup.bash
ros2 launch contact_glove contact_glove_with_rviz.launch.xml
```

サーバーが起動すると `[server] Client registered at 127.0.0.1:25788` が表示され、RViz2 にスケルトンが描画されます。

モックサーバーで `get_retarget_profile` を照会すると、左右の固定UUID（末尾 `...0001` / `...0002`）は成功します。
未登録の有効UUIDは `status: 1`、末尾 `...0003` は意図的に応答しないためタイムアウトを確認できます。


### 配布用 ZIP の生成

`scripts/package_ros2.sh` は、同じROS2ディストリビューション向けの
`contactglove-ros2-bridge` と `contactglove-ros2-msgs` のDEBをルートに同梱した配布用ZIPを生成します
（`packaging/README.md` を `README.md` として同梱します）。
配布ZIPには、README、ルートのbridge・msgs DEB、ブリッジとメッセージを含む `install/`、
C++ランタイムDEBと出所情報を含む `lib/`、
インストール補助スクリプト、ライセンス文書が入ります。
両ROS2パッケージにも最小README日英・ライセンス文書をインストールします。フルガイド・ユーザーマニュアル・APIリファレンスはWebで管理します。
配信側ではbridge・msgs・C++ランタイムの3つのDEBを、購読側ではmsgsだけをインストールします。

```bash
sudo apt-get install -y zip unzip dpkg-dev
source /opt/ros/jazzy/setup.bash
# 上の SDK_BUILD_DIR のDEBと証跡を使います。
bash scripts/package_ros2.sh jazzy noble
```

詳細は `scripts/package_ros2.sh` 内のコメント、ZIPに同梱されたdebの検証方法は
`scripts/verify_ros2_deb_install.sh` を参照してください。

## ライセンス

自社の ROS 2 driver・messages・サンプル・SDK 文書は [Apache-2.0](LICENSE.md) です。
第三者コンポーネントの条件は維持し、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) に oscpack の全文を収録しています。
ROS 2 依存パッケージのライセンスは、それぞれの提供元を確認してください。

同梱C++ SDKは固定submoduleからROS2側でビルドしたDEBです。

## C++ SDKの出所とチェックサム

配布ZIPの `lib/` には、C++ランタイムDEBと出所情報を格納します。
`$SDK_BUILD_DIR/sdk-provenance.json` はビルド時に生成され、配布ZIPの
`lib/sdk-provenance.json` に配置されます。ソースコミット、ビルドID、コンパイラーと
CMakeのバージョン、DEBの制御フィールド、SHA-256を記録します。
ZIPを展開したルートで次を実行し、結果を `lib/sdk-provenance.json` の `sha256` と照合してください。

```bash
sha256sum lib/contactglove-sdk-v2_*.deb
```

C++ SDKのビルドは、SDKに記録された固定リビジョンのoscpackを取得します。
第三者コンポーネントには、それぞれのライセンス条件が適用されます。

### 公開C++ SDKと配布パッケージ

C++ SDKの取得先とgitlinkは公開版に固定しています。CIは認証情報を渡さずに取得し、
新規導入・所有権・ELFリンク・msgs利用・削除/再導入・UDP/DDS回復を検証します。
bridgeは同じUbuntu向けの公式C++ DEB `1.0.0-0jammy` / `1.0.0-0noble`、または
そのZIPに同梱されたC++ DEBの完全版だけを受け入れます。単なる版の範囲では
別Ubuntu向けのDEBも入るため、検証した2つの版を明示しています。
新しいC++版へ更新するときは、対応するbridgeも再ビルド・検証してください。
ABIのメジャーが変わる2.0.0以上も受け入れません。同梱SDKは公開ソースをROS2 CIで
再ビルドしたもので、公式Release DEBと同じバイト列だとは扱いません。

このCIはローカルDEBによる試験です。APTサーバーへの到達性や実機動作を
検証するものではありません。

### 1.0.0への更新

1.0.0ではC++ランタイムの共有ライブラリ名が `.so.0` から `.so.1` に変わります。
旧bridgeを残してC++ランタイムだけを更新しないでください。bridge・msgs・C++ランタイムを
同じUbuntu向けの互換セットとして更新する必要があります。旧0.2.5の実配布物一式からの
更新は現在のCIでは検証していません。導入先で旧版から更新する前に、実際のパッケージ構成を
使った使い捨て環境で検証してください。
