# ContactGlove ROS2 SDK V2

[English](README.md) | 日本語

[ContactGlove C++/C/Rust SDK V2](https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp)を介してDivingStationと通信し、ContactGlove3 ProのデータをROS2トピック・サービスとして提供します。

## 対応環境

- Ubuntu 22.04 LTS / ROS2 Humble / amd64、またはUbuntu 24.04 LTS / ROS2 Jazzy / amd64。
- ブリッジにはDivingStation v2以降とC++ランタイムが必要です。購読専用の別PC・コンテナでは、C++ランタイムを必要としないメッセージ単独パッケージを使用できます。

## APTからインストールする

対応するROS2とそのAPTリポジトリを先に設定し、共通の[APTリポジトリの初回設定](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/apt-repository)を行ってください。[ROS2のAPTガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2#aptからインストールする)に従ってパッケージ一覧を更新し、候補バージョンと配信元を確認してから、用途に合わせてパッケージを選びます。

- 配信側: `sudo apt-get install contactglove-ros2-bridge`。同じバージョンのmsgsと互換性のあるC++ランタイムも依存関係としてインストールされます。
- 購読専用の別PC・コンテナ: `sudo apt-get install contactglove-ros2-msgs`。ブリッジとC++ランタイムはインストールされません。

更新、ターミナルの設定、ZIPとAPTの併用に関する注意点は、[ROS2のAPTガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2#aptからインストールする)を参照してください。

## ドキュメント

- [SDKガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2)
- [ユーザーマニュアル](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/user-manual)
- [APIリファレンス](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/api)

ZIPを利用する場合のブリッジ・購読専用パッケージのインストールと最小の起動例は、[ZIPの導入手順](packaging/README_JA.md)に記載しています。詳しい利用方法はWebドキュメントで管理しています。

ソースからのビルド、テスト、配布物の生成、C++ SDKの出所情報は[DEVELOPMENT_JA.md](DEVELOPMENT_JA.md)を参照してください。[モックサーバー](scripts/mock_server/README_JA.md)は合成データを生成するため、実機なしでローカルの動作を確認できます。

## ライセンス

[Apache-2.0](LICENSE.md)です。[NOTICE.md](NOTICE.md)と[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)も参照してください。第三者コンポーネントには、それぞれのライセンス条件が適用されます。
