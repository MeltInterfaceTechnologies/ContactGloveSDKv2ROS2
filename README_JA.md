# ContactGlove ROS2 SDK V2

[English](README.md) | 日本語

[ContactGlove C++/C/Rust SDK V2](https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp)を介してDivingStationと通信し、ContactGlove3 ProのデータをROS2トピック・サービスとして提供します。

## 対応環境

- Ubuntu 22.04 LTS / ROS2 Humble / amd64、またはUbuntu 24.04 LTS / ROS2 Jazzy / amd64。
- ブリッジにはDivingStation v2以降とC++ランタイムが必要です。購読専用の別PC・コンテナでは、C++ランタイムを必要としないメッセージ単独パッケージを使用できます。

## ドキュメント

- [SDKガイド](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2)
- [ユーザーマニュアル](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/user-manual)
- [APIリファレンス](https://docs.melt-interface-technologies.com/ja/docs/contact/sdks/contact-glove-v2-ros2/api)

ブリッジ・購読専用パッケージのインストールと最小の起動例は[配布パッケージの導入手順](packaging/README_JA.md)を参照してください。詳しい利用方法はWebドキュメントで管理しています。

ソースからのビルド、テスト、配布物の生成、C++ SDKの出所情報は[DEVELOPMENT_JA.md](DEVELOPMENT_JA.md)を参照してください。[モックサーバー](scripts/mock_server/README_JA.md)は合成データを生成するため、実機なしでローカルの動作を確認できます。

## ライセンス

[Apache-2.0](LICENSE.md)です。[NOTICE.md](NOTICE.md)と[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)も参照してください。第三者コンポーネントには、それぞれのライセンス条件が適用されます。
