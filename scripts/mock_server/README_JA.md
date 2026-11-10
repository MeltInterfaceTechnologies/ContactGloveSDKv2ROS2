# Mock DivingStation server

[English](README.md) | 日本語

グローブやDivingStationを使わずに動作を確認するためのローカルモックです。
引数なしで起動すると左右の手の動きを合成し、`HandSkeleton`、`HandSkeletonRaw`、
`Ergonomics`、`Device` のOSCメッセージを送信します。
合成した動きは表示確認用であり、実測データやキャリブレーションモデルではありません。

## 合成データで起動

Ubuntu 22.04 / 24.04では、リポジトリのルートから次を実行してください。
依存パッケージは仮想環境にインストールし、UbuntuのシステムPythonには追加しません。

```sh
sudo apt-get install python3-venv
python3 -m venv /tmp/contactglove-mock-venv
/tmp/contactglove-mock-venv/bin/python -m pip install python-osc
/tmp/contactglove-mock-venv/bin/python scripts/mock_server/server.py
```

待ち受け先は `127.0.0.1:25791`（UDP）のみで、登録されたループバックのクライアントに送信します。
ROS2ノードも同じホスト、または同じネットワーク名前空間で実行してください。
同じポートでDivingStationを同時に起動しないでください。
別のターミナルで、ビルド済みのROS2ワークスペースを読み込んで起動します。

```sh
source install/setup.bash
ros2 launch contact_glove contact_glove_with_rviz.launch.xml
```

終了するにはCtrl+Cを押します。実機を使う場合はモックの代わりにDivingStationを起動してください。

## プロファイル照会とテスト

末尾が `0001` / `0002` の固定UUIDは、モックの左右プロファイルを返します。
未登録の有効UUIDはstatus 1、末尾 `0003` のUUIDはタイムアウト確認用に応答しません。
プロファイル応答は登録済みのローカルクライアント全員に送信します。

```sh
/tmp/contactglove-mock-venv/bin/python -m unittest discover -s scripts/mock_server -p 'test_*.py' -v
```
