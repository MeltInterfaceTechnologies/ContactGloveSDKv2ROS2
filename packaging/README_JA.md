# ContactGlove ROS2 SDK V2

[English](README.md) | 日本語

このREADMEでは配布ZIPからの導入を説明します。APTを利用する場合は、共通の[リポジトリの初回設定](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/apt-repository)を行い、[ROS2の導入・更新ガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2#aptからインストールする)を参照してください。

## 必要環境

- 対応機種: ContactGlove3 Pro。
- Ubuntu 22.04 LTS / ROS2 Humble / amd64（x86-64）、またはUbuntu 24.04 LTS / ROS2 Jazzy / amd64（x86-64）
- ROS2とそのAPTリポジトリを設定済みであること。OSとROS2に合うZIPを使用します。ARM64や他のOS・ROS2は、この配布物の対象外です。
- 配信側にはDivingStation v2以降と同梱C++ランタイム1.0.0が必要です。購読専用の環境では、DivingStationとC++ランタイムは不要です。

## ZIPからのインストールと起動

ZIPを展開したディレクトリから実行します。グローブのデータを配信する環境には、3つのローカルDEBを明示してインストールします。

```bash
sudo apt update
sudo apt install ./lib/contactglove-sdk-v2_*.deb \
  ./contactglove-ros2-msgs_*.deb ./contactglove-ros2-bridge_*.deb
```

購読専用の別PC・コンテナには、`contact_glove_msgs` のインターフェースを提供する `contactglove-ros2-msgs` だけをインストールします。

```bash
sudo apt update
sudo apt install ./contactglove-ros2-msgs_*.deb
```

新しいターミナルではROS2をsourceしてください。配信側ではDivingStationを起動してグローブを接続し、ブリッジを起動します。

```bash
# Ubuntu 24.04 / Jazzy。Ubuntu 22.04 / Humbleでは /opt/ros/humble/setup.bash を使用する。
source /opt/ros/jazzy/setup.bash
ros2 launch contact_glove contact_glove.launch.xml
```

購読専用の環境ではROS2だけをsourceし、ブリッジを起動したりZIPの `install/` をsourceしたりしません。配信側と同じROS2ディストリビューション、互換性のあるメッセージ定義、同じ `ROS_DOMAIN_ID` を使用し、DDSの探索と通信を許可してください。

## Webドキュメント

- [SDKガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2): APT・ZIPからの導入、更新、ZIPのoverlay利用
- [ユーザーマニュアル](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/user-manual): 接続、可視化、トラブル対応
- [APIリファレンス](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/api)

Apache-2.0です。ライセンスと第三者コンポーネントの条件は、同梱の `LICENSE.md`、`NOTICE.md`、`THIRD_PARTY_NOTICES.md` を参照してください。
