# TwinCAT + PyADS + Apache IoTDB + Grafanaによるコンテナアプリケーション

このリポジトリは、TwinCATのIoT向けプロトコルとして開発された ADS-over-MQTT を使い、工場などに置かれたBeckhoff製 IPC から稼働中の制御データを時系列データベースに保存し、Grafana上に表示する実装サンプルです。次図の上部のコンテナ群をdocker-composeで構築します。

![](assets/distributed_components.svg)

> [!note]
> 本システムは、PythonがADS通信を行うためのパッケージpyadsを使用してTwinCATと接続します。この際、ads-over-mqttを通じて通信を行うために、pyadsが稼働するコンテナ上にもTwinCATランタイムを動作させています。（図中のTcSystemServiceUm）pyadsは、このプロセスが動作している上で、 TcAdsDll.so をリンクしてads-over-mqttによるADS接続を実現しています。
>
> これらのTwinCAT関連ソフトウェアをインストールするため、コンテナビルド時にTwinCAT RT Linuxのaptリポジトリを登録し、ここからパッケージをダウンロードするためのMyBeckhoffのアカウント設定が事前に必要となります。


> [!important]
> サポートについて
> * 本システムはライセンス条項に基づき、いかなる保証を行いません。
> * Beckhoff製IPCの導入をご検討の上、本システムの活用をご検討されている方には技術的なご相談にお応えいたします。ご遠慮なくお問い合わせください。
> * また第三者企業様が十分に検証を行われた上でサービス、または、製品化していただくことはなんら妨げません。この場合も開発元であるベッコフオートメーション株式会社、および本ソフトウェア作者は一切責任を負いません。

## 動作環境

docker-ce が動作する環境が必要です。クラウドやオンプレミスのさまざまなLinux Distributionだけでなく、Windows上のWSL上でも動作可能です。

ただし、本サンプルではIPCと本システム間の通信に使用するMQTTをセキュアな設定にはしておりませんので、クラウド上での使用には適していません。別途TLSの設定が必要です。

## 設置手順

### 準備

1. [Docker-ceをインストール](https://beckhoff-jp.github.io/TwinCATHowTo/linux/docker/install_docker.html)してください。
2. 本システムを稼働させるコンピュータに GNU make をインストールしてください。debian系のパッケージマネージャを例に次のとおりコマンド発行してインストールします。

    ``` bash
    sudo apt install --yes make
    ```

3. Beckhokffのサイトにて、[MyBeckhoffのアカウントを作成](https://www.beckhoff.com/ja-jp/mybeckhoff-registrierung/index.aspx)してください。
4. サンプルのIPCプロジェクトである[ジョブフレームワーク](https://github.com/Beckhoff-JP/PLC_JobManagementFramework)プロジェクトをIPC等に書き込んで動作できる状態にしておきます。

> [!note]
> EtherCATの実ネットワークであるEL7201やモータが接続されていない場合は、EtherCATを無効化させ、仮想軸をシミュレータモードにしてください。
> Visualization画面から`Power`ボタンを押したあと、`Start`ボタンを押せばシーケンスを連続開始します。
>
> ![](assets/plc_visualization.png)


### リポジトリの展開と設定

リポジトリをクローンなど行ってターゲットのコンピュータ上に展開し、2か所設定を行います。

1. MyBeckhoffアカウントの設定

    次のファイルを編集し、MyBeckhoffで作成したアカウントのメールアドレスとパスワードを設定します。

    ``` bash
    twincat_data_collector/apt-config/bhf.conf

    machine deb.beckhoff.com login <MyBeckhoffメールアドレス> password <MyBeckhoffパスワード>
    machine deb-mirror.beckhoff.com login <MyBeckhoffメールアドレス> password <MyBeckhoffパスワード>
    ```
   
2. 自分とターゲットIPCのAMS NET IDをそれぞれ `docker-compose.yaml` ファイルに定義します。自分のAMS NET IDは6桁の1～255までの数字の組み合わせでADSネットワーク内で重複が無ければ何でも構いません。迷ったら IPアドレスに `.1.1` を付け加えたものにしておけばよいでしょう。

    ``` yaml
    /docker-compose.yaml
      :
     data_acquisition:
      image: data_acquisition:latest
      container_name: data_acquisition
      restart: unless-stopped
      hostname: data_acquisition
      depends_on:
        iotdb:
          condition: service_healthy
      privileged: true
      environment:
        - ROUTER_ADDRESS=localhost
        - TARGET_AMSID=15.15.15.15.1.1  <-- IPC側のIDをここに定義
        - MY_AMSID=192.168.20.20.1.1  　<-- 自分のIDをここに定義
        - IOTDB_HOST=iotdb
        - PCI_DEVICES=NONE
    ```

### Dockerイメージのビルド

本リポジトリのディレクトリツリー内の次の場所で、`sudo make build-image` コマンドを入力します。

``` bash
cd twincat_data_collector
sudo make build-image
```

パスワードを入力すると、Docker buildが開始されます。ビルドにはインターネット接続が必要です。

> [!tip]
> sudo make build-image コマンドで実行している中身は次のとおりです。これを簡素化するためにmakeコマンドを実行しています。
> 
> ``` bash
>  cd twincat_data_collector
> sudo docker build --secret id=apt,src=./apt-config/bhf.conf --network host -t data_acquisition 。
>  ```


### MQTTブローカへのアクセスポート1883を開放

本システムには、MQTTブローカであるmosquittoサーバが稼働するコンテナが内包されています。このサーバへのアクセスを外部から受け付けられるように、設置するコンピュータのファイヤウォール設定を行います。

ここでは、debian 13 (trixie) で採用されているnftablesを例に説明します。

1. `/etc/nftables.conf.d/` ディレクトリ以下に新規のファイル `60-mosquitto-container.conf` を作成します。

    ``` bash
    sudo touuch /etc/nftables.conf.d/60-mosquitto-container.conf
    ```

2. 作成したファイルをテキストエディタで編集します。（vi や nanoなど）

    ``` conf
    table inet filter {
      chain input {
        tcp dport 1883 accept
      }
      chain forward {
        type filter hook forward priority 0; policy drop;
        tcp sport 1883 accept
        tcp dport 1883 accept
      }
    }
    ```

3. 設定を反映します。

    ```bash
    sudo nft -f /etc/nftables.conf.d/60-mosquitto-container.conf
    ```

4. systemdでも反映します。

    ``` bash
    sudo systemctl restart nftables
    ```


### IPC側の設定

IPC側の設定は極めて簡単です。次のファイルを作成し、次の場所に置きます。


* Windowsの場合（Buuild 4024 まで）

    ``` bash
    C:\TwinCAT\3.1\Target\Routes\mqtt.xml
    ```

* Windowsの場合（Build 4026以後）

    ``` bash
    C:\Program Files(x86)\Beckhoff\TwinCAT\3.1\Target\Routes\mqtt.xml
    ```

* LinuxやTwinCAT BSDの場合

    ``` bash
    /etc/TwinCAT/3.1/Target/Routes/mqtt.xml
    ```

> [!note]
> Targetディレクトリ以下のRoutesディレクトリは存在しないことが多いので新規作成してください。


mqtt.xmlファイルの中身は次の通り定義します。Adressタグの中に、mosquittoコンテナを配置したサーバのIPアドレスを設定してください。

``` xml
<?xml version="1.0" encoding="utf-8"?>
<TcConfig xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:noNamespaceSchemaLocation="http://www.beckhoff.com/schemas/2015/12/TcConfig">
<RemoteConnections>
    <Mqtt>
        <Address Port="1883">ここに本システムが稼働するコンピュータのIPアドレスを設定</Address>
        <Topic>AdsOverMqtt</Topic>
    </Mqtt>
</RemoteConnections>
</TcConfig>

```

## コンテナを起動

> [!important]
> 事前にIPCにジョブフレームワークプロジェクトをActive configurationを行ってRUNさせてください。
> 
> また、本コンテナシステムが稼働しているコンピュータとIPCのEthernetポートと接続し、TCP/IP接続できるようにしておいてください。

本システムを稼働させるコンピュータに展開したリポジトリの最上位である `docker-compose.yaml` ファイルがある場所で、次のコマンドを発行します。この際、インターネットから主要なアプリケーションを自動インストールしますので、事前にインストール接続できるようにしておいてください。


```bash
$ sudo docker compose up -d
```

Docker composeはデーモンとして機能しますので、以後は再起動しても自動的に起動します。また、無効化したい場合は、同じく `docker-compose.yaml` ファイルがある場所で次のコマンドを発行します。

```bash
$ sudo docker compose down
```

これで以後自動起動しなくなります。一時的に終了したい場合は

```bash
$ sudo docker compose stop
```

とし、再度起動する場合は、


```bash
$ sudo docker compose start
```

とします。stopで停止させた場合は、再起動すると自動的に起動します。

docker composeを起動すると、 `docker-compose.yaml` の定義に従って、順番に必要なコンポーネントをまとめて起動します。すべて成功すると次のとおり表示されます。

```bash
$ sudo docker compose up -d
[sudo] password for Administrator:
[+] up 4/4
  ✔ Container iotdb            Healthy                                    0.5s
  ✔ Container grafana          Running                                    0.0s
  ✔ Container mosquitto        Running                                    0.0s
  ✔ Container data_acquisition Running                                    0.0s
```

grafanaや、pythonで動作するdata_acquisitionは、データベースソフトであるiotdbが起動し、接続テストをパスしないと起動できません。テストの結果合格すると`Healthy`と表示されます。何度かリトライするも失敗すると次のとおり現れます。

``` bash

[+] up 5/5
 ✔ Network container-network  Created                                     0.0s
 ✔ Container mosquitto        Started                                     0.3s
 ✘ Container iotdb            Error dependency iotdb failed to start    201.3s
 ✔ Container grafana          Created                                     0.1s
 ✔ Container data_acquisition Created                                     0.1s
dependency failed to start: container iotdb is unhealthy
```

このようなケースに遭遇した場合は、いちど `sudo docker compose down`を行い、時間を置いたあと再度試してみてください。特にIoTDBはコネクションなどのキャッシュが残っていると、次回再起動がうまくいかないことがあることが確認されています。

Dockerにおける各コンテナの稼働状況は、次のコマンドで確認できます。

```
$ sudo docker ps
[sudo] password for Administrator:
CONTAINER ID   IMAGE                        COMMAND                  CREATED             STATUS                    PORTS                                                                                          NAMES
520713d03ac3   data_acquisition:latest      "/usr/bin/supervisord"   About an hour ago   Up 59 minutes                                                                                                            data_acquisition
0e8e25d5b0f1   grafana/grafana-enterprise   "/run.sh"                About an hour ago   Up 59 minutes             0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp                                                    grafana
3747405b622d   eclipse-mosquitto:latest     "/docker-entrypoint.…"   About an hour ago   Up 59 minutes             0.0.0.0:1883->1883/tcp, [::]:1883->1883/tcp                                                    mosquitto
afccae63e91e   apache/iotdb:latest          "/usr/bin/dumb-init …"   About an hour ago   Up 59 minutes (healthy)   0.0.0.0:6667->6667/tcp, [::]:6667->6667/tcp, 0.0.0.0:18080->18080/tcp, [::]:18080->18080/tcp   iotdb
```

このように、docker composeによってさまざまなコンテナが協調して動作しています。次節ではこのうち、データベースソフトウェアである Apache IoTDB のコンテナに入ってデータベースへの接続確認を行ってみます。IoTDBは、NAMES列にある `iotdb` がコンテナ名であることがわかります。

## IoTDBで接続確認

起動ができたら、次のコマンドでiotdbコンテナ内にログインします。

``` bash
$ docker exec -it iotdb bash 
root@iotdb:/iotdb/sbin#
```

上記により、`iotdb` コンテナ内にbashシェルで入ることができます。

続いて次のコマンドによりiotdbサーバへ接続するクライアント端末が起動します。

``` bash
root@iotdb:/iotdb/sbin# start-cli.sh -h iotdb
---------------------
Starting IoTDB Cli
---------------------
 _____       _________  ______   ______
|_   _|     |  _   _  ||_   _ `.|_   _ \
  | |   .--.|_/ | | \_|  | | `. \ | |_) |
  | | / .'`\ \  | |      | |  | | |  __'.
 _| |_| \__. | _| |_    _| |_.' /_| |__) |
|_____|'.__.' |_____|  |______.'|_______/  version 2.0.8 (Build: b88b5dc)


Successfully login at iotdb:6667
IoTDB>
```

これにより、IoTDBのクエリプロンプトが現れます。最新のすべての時系列データの1行を収集するには、次のクエリを発行します。

``` sql
IoTDB> select last * from root.demo1.*
```

次のとおり、すべての時系列データがマイクロ秒精度の時刻と共に一覧されます。

``` sql
IoTDB> select last * from root.demo1.*
+---------------------------+-------------------------------------------+--------------------------------------+--------+
|                       Time|                                 Timeseries|                                 Value|DataType|
+---------------------------+-------------------------------------------+--------------------------------------+--------+
|2026-06-27T16:04:25.052975Z|               root.demo1.job.job_namespace|                           /260627/197|    TEXT|
|2026-06-27T16:04:25.052975Z|                      root.demo1.job.job_id|                        /260627/197/32|    TEXT|
|2026-06-27T16:04:25.052975Z|                     root.demo1.job.subject|                          Back to home|    TEXT|
|2026-06-27T16:04:25.052975Z|                  root.demo1.job.num_of_job|                                     0|   INT32|
|2026-06-27T16:04:25.052975Z|                   root.demo1.job.old_state|                               process|    TEXT|
|2026-06-27T16:04:25.052975Z|                   root.demo1.job.new_state|                                  quit|    TEXT|
|2026-06-27T16:04:25.052975Z|                 root.demo1.job.record_time|0x343534343736333935313035373436393434|    BLOB|
|2026-06-27T16:04:23.458973Z|              root.demo1.axis1.ModuloSetPos|                     80.19736321326081|  DOUBLE|
|2026-06-27T16:04:23.458973Z|             root.demo1.axis1.AbsPhasingPos|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|             root.demo1.axis1.ModloActTurns|                                     3|   INT32|
|2026-06-27T16:04:23.458973Z|      root.demo1.axis1.AxisModeConfirmation|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                  root.demo1.axis1.UserData|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|    root.demo1.axis1.ActiveControlLoopIndex|                                     0|   INT32|
|2026-06-27T16:04:23.458973Z|                   root.demo1.axis1.PosDiff|                  0.015964508056640625|  DOUBLE|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.DcTimeStamp|                            1983964888|   INT64|
|2026-06-27T16:04:23.458973Z|       root.demo1.axis1.ActTorqueDerivative|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|          root.demo1.axis1.ControlLoopIndex|                                     0|   INT32|
|2026-06-27T16:04:23.458973Z|                    root.demo1.axis1.AxisId|                                     1|   INT64|
|2026-06-27T16:04:23.458973Z|                   root.demo1.axis1.SetJerk|                                  -0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|             root.demo1.axis1.ModloSetTurns|                                     3|   INT32|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.HomingState|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                    root.demo1.axis1.SetPos|                    1160.1973632132608|  DOUBLE|
|2026-06-27T16:04:23.458973Z|                    root.demo1.axis1.ActPos|                    1162.6805877685547|  DOUBLE|
|2026-06-27T16:04:23.458973Z|                     root.demo1.axis1.CmdNo|                                  4118|   INT32|
|2026-06-27T16:04:23.458973Z|                   root.demo1.axis1.SetVelo|                               -1000.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|         root.demo1.axis1.TouchProbeCounter|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|              root.demo1.axis1.TorqueOffset|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|                root.demo1.axis1.SafEntries|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                root.demo1.axis1.StateDWord|                              34608385|   INT64|
|2026-06-27T16:04:23.458973Z|                 root.demo1.axis1.ActTorque|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|              root.demo1.axis1.ActPosModulo|                     82.68058776855469|  DOUBLE|
|2026-06-27T16:04:23.458973Z|                 root.demo1.axis1.SetTorque|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.CoupleState|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                   root.demo1.axis1.ErrCode|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                 root.demo1.axis1.AxisState|                                     3|   INT64|
|2026-06-27T16:04:23.458973Z|                   root.demo1.axis1.ActVelo|                   -1002.0872617317865|  DOUBLE|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.StateDWord2|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                  root.demo1.axis1.CmdState|                                   513|   INT32|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.StateDWord3|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                 root.demo1.axis1.TargetPos|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|               root.demo1.axis1.OpModeDWord|                            2569080835|   INT64|
|2026-06-27T16:04:23.458973Z|                root.demo1.axis1.SvbEntries|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|                    root.demo1.axis1.SetAcc|                                  -0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|           root.demo1.axis1.TouchProbeState|                                     0|   INT64|
|2026-06-27T16:04:23.458973Z|       root.demo1.axis1.SetTorqueDerivative|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|                    root.demo1.axis1.ActAcc|                                   0.0|  DOUBLE|
|2026-06-27T16:04:23.458973Z|root.demo1.axis1.ActPosWithoutPosCorrection|                    1162.6805877685547|  DOUBLE|
+---------------------------+-------------------------------------------+--------------------------------------+--------+
Total line number = 47
It costs 0.209s
IoTDB>
```

`data_acquisition` コンテナで実装されたPythonスクリプトは、構造体データモデルをもとにIoTDBのスキーマ定義を自動化し、また、モーションタスクやPLCタスクのサイクル周期をすべてIoTDBに書き込むことができます。

クエリの詳細は[こちらのドキュメント](https://iotdb.apache.org/UserGuide/V1.2.x/User-Manual/Query-Data.html)を参照してください。

## Grafanaセットアップ

1. 次のURLへアクセスし、初回はユーザ名 `admin` パスワード空白でログインします。

    ``` url
    http://コンテナを立てたコンピュータのIPアドレス:3000/
    ```

    つづいて初期パスワード設定を求められます。任意のパスワードを設定してください。

2. 最初にIoTDBとのコネクション設定を行います。

    ![](assets/grafana/setup1.png)

3. 新しいコネクションから、検索窓でiotdbを入力してデータソースからApache IoTDBを選択します。

    ![](assets/grafana/setup2.png)

4. 右上の Add new data source を選択します。

    ![](assets/grafana/setup3.png)

5. 必要項目を入力し、Save & test を押します。

    |項目|設定|
    |--|--|
    |URL|http://iotdb:18080|
    |username|root|
    |password|root|

    ![](assets/grafana/setup4.png)

6. Data source is working と現れたら接続成功です。続いて、右上の `+` アイコンからサブメニューを出現させ、import dashboard を選びます。

    ![](assets/grafana/setup5.png)

7. Upload dashboard JSON file 部分をクリックし、現れるファイル選択ウィンドウから、同梱している `grafana_dashboard.json` を読み込ませます。

    ![](assets/grafana/setup6.png)

8. ダッシュボード画面に3つのチャートブロックが現れます。初期状態では非表示状態となっています。右上のメニューアイコンをクリックし、Editを選びます。

    ![](assets/grafana/setup7.png)

9. IPCからデータを受け取り、IoTDBに最新データが記録されていると、しばらくしてグラフプレビューが表示されます。無事表示されたら、右上の Save ボタンを押して保存します。

    ![](assets/grafana/setup8.png)

> [!tip]
> なお、左下のクエリ設定画面では、さきほど接続確認を行ったSQL文を入力することでグラフに表示されるデータの内容が変わります。また、右フレームの最上部にある `State timeline` の右側にある `Change` を押すと、現在のチャートの種類である状態表示バーから、違う種類のチャートに変更することも可能です。詳しくは[Apache IoTDB Grafana Pluginドキュメント](https://iotdb.apache.org/UserGuide/latest/Ecosystem-Integration/Grafana-Plugin.html#_2-how-to-use-grafana-plugin)をご覧ください。

10. 同様に2段目、3段目も同様の手順を行ってすべて表示できる状態にします。

    ![](assets/grafana/setup9.png)

## SQLを使った分析

Apache IoTDBは、ツリーモードとテーブルモードの二つを持ちます。デフォルトはツリーモードとなっており、現実世界のデバイス構成のように親子関係でツリーモデルを定義し、そこに存在する設定値や制御値、計測値などを時系列データとして記録することができます。

ただ、記録したデータを活用するには、SQLを使ったさまざまな分析が必要です。この場合は、テーブルモードを使ってデータの取り出しを行います。

![](https://iotdb.apache.org/img/tree-to-table-en-1.png)

> [!note]
> [こちらのサイト](https://iotdb.apache.org/UserGuide/latest-Table/User-Manual/Tree-to-Table_apache.html)からの抜粋

ツリーモードとテーブルモードの相互の切り替えは、クライアントコマンド、または、APIにより行います。詳しくは[こちら](https://iotdb.apache.org/UserGuide/latest/Background-knowledge/Data-Model-and-Terminology_apache.html#_2-2-model-selection)を参照してください。

下記はデフォルトのツリーモードでデータベースを一覧した状態です。本コンテナシステムのPythonのスクリプトの初期化処理により、自動的に `root` というデータベースと、 `demo1` というタイムシリーズが作成されています。

``` SQL
IoTDB> show databases
+------------+-----------------------+---------------------+-------------------+---------------------+
|    Database|SchemaReplicationFactor|DataReplicationFactor|TimePartitionOrigin|TimePartitionInterval|
+------------+-----------------------+---------------------+-------------------+---------------------+
|root.__audit|                      1|                    1|                  0|            604800000|
|  root.demo1|                      1|                    1|                  0|            604800000|
+------------+-----------------------+---------------------+-------------------+---------------------+
Total line number = 2
It costs 0.025s
```

ここでテーブルモードへ切り替えます。

``` SQL
IoTDB> set SQL_DIALECT=TABLE
```

初期状態では、システムのデフォルトのデータベースのみで、ツリーモードで記録されたデータへアクセスできるデータベースが存在しません。

``` SQL
IoTDB> show databases
+------------------+-------+-----------------------+---------------------+---------------------+
|          Database|TTL(ms)|SchemaReplicationFactor|DataReplicationFactor|TimePartitionInterval|
+------------------+-------+-----------------------+---------------------+---------------------+
|information_schema|    INF|                   null|                 null|                 null|
+------------------+-------+-----------------------+---------------------+---------------------+
Total line number = 1
It costs 0.054s
```

このため、まずはデータベース`viewdb`を新規で作成します。

``` SQL
IoTDB> create database viewdb
```

作成したviewdbに対してテーブルを作成します。作成するテーブルは、新たにデータを記録するためのものではなく、 **すでに記録されたツリーモードのデータへの参照テーブルです。** つまり、ビューテーブルを作成する、と言い換えられます。

すでに時系列データが記録されている `root.demo1.job` のうち、分析に必要なデータを登録したビューテーブルを作成します。この際、ttlにはマッピングする期間をミリ秒精度で定義します。下記の例は、7日 x 24時間 x 60分 x 60秒 x 1000 ミリ秒 の値を設定しています。

``` SQL
IoTDB> create or replace view viewdb.job (
    subject String FIELD, 
    old_state String FIELD, 
    new_state String FIELD, 
    job_namespace String FIELD, 
    job_id String FIELD
    ) with (ttl=604800000) AS root.demo1.job.**;
```

作成したビューテーブルは、SQLでクエリによりデータを取り出すことができます。

``` SQL
IoTDB> select * from viewdb.job limit 10
+---------------------------+-------------------+----------------+---------+-------------+--------------+
|                       time|            subject|       old_state|new_state|job_namespace|        job_id|
+---------------------------+-------------------+----------------+---------+-------------+--------------+
|2026-06-26T07:02:56.317648Z|100 deg/s 5 seconds|wait_for_process|  process|  /260626/752|/260626/752/28|
|2026-06-26T07:02:57.517648Z|100 deg/s 5 seconds|         process|     quit|  /260626/752|/260626/752/28|
|2026-06-26T07:02:57.527649Z|100 deg/s 5 seconds|            quit|   finish|  /260626/752|/260626/752/28|
|2026-06-26T07:02:57.537644Z|      Move velocity|wait_for_process|  process|  /260626/752|/260626/752/29|
|2026-06-26T07:02:58.187648Z|      Move velocity|         process|     quit|  /260626/752|/260626/752/29|
|2026-06-26T07:02:58.197646Z|      Move velocity|            quit|   finish|  /260626/752|/260626/752/29|
|2026-06-26T07:02:58.207649Z|800 deg/s 5 seconds|wait_for_process|  process|  /260626/752|/260626/752/30|
|2026-06-26T07:03:03.217649Z|800 deg/s 5 seconds|         process|     quit|  /260626/752|/260626/752/30|
|2026-06-26T07:03:03.227644Z|800 deg/s 5 seconds|            quit|   finish|  /260626/752|/260626/752/30|
|2026-06-26T07:03:03.237651Z|               STOP|wait_for_process|  process|  /260626/752|/260626/752/31|
+---------------------------+-------------------+----------------+---------+-------------+--------------+
Total line number = 10
It costs 0.045s
```

同様にaxis1もビューテーブルを作成します。

``` SQL
IoTDB> create or replace view viewdb.axis1 (
    ActPos double FIELD, 
    SetPos double FIELD, 
    ActVelo double FIELD, 
    SetVelo double FIELD, 
    PosDiff double FIELD
    ) with (ttl=604800000) AS root.demo1.axis1.**
```

> [!tip]
> なお、ツリーモードにおいてサブデバイスが多層的に構成されている場合、その階層に応じたデバイス名がタグ列として定義することができます。
> 
> たとえば、今回のツリーモデルはdemo1の直下にいきなりaxis1がぶら下がっていますので該当しませんが、もし複数軸がある場合、`demo1.axes.axis1`, `demo1.axes.axis2`.. という具合に軸を束ねる親デバイス `axes` 以下にaxis1やaxis2といったタイムシリーズを構築することが望ましいです。この場合、下記のとおり、`axis_name` という文字列型で `TAG` 属性のカラムを定義すると `axis1` や `axis2` という具合に振り分けられます。
> ``` SQL
> IoTDB> CREATE OR REPLACE VIEW viewdb.axes (
>    axis_name String TAG,
>    actpos DOUBLE FIELD,
>    setpos DOUBLE FIELD,
>    actvelo DOUBLE FIELD,
>    setvelo DOUBLE FIELD,
>    posdiff DOUBLE FIELD
>    ) WITH (ttl=604800000) AS root.demo1.axes.**
> ```

こちらもSQLクエリでデータを取り出すことができます。

``` SQL
IoTDB> select * from viewdb.axis1 limit 10
+---------------------------+------------------+------------------+------------------+-------+--------------------+
|                       time|            actpos|            setpos|           actvelo|setvelo|             posdiff|
+---------------------------+------------------+------------------+------------------+-------+--------------------+
|2026-06-26T07:02:55.933646Z| 408.1681823730469|  408.424313789285| 102.2692591055467|  100.0|0.005321502685546875|
|2026-06-26T07:02:55.934148Z|408.21922302246094| 408.4743137892851|102.26030861614565|  100.0|0.004062652587890625|
|2026-06-26T07:02:55.934648Z|408.27049255371094|408.52431378928515| 102.2735826106149|  100.0|0.002803802490234375|
|2026-06-26T07:02:55.935148Z|  408.321533203125| 408.5743137892852|102.26442624002013|  100.0| 0.00171661376953125|
|2026-06-26T07:02:55.935647Z| 408.3732604980469| 408.6243137892852| 102.3211006973406|  100.0|   2.288818359375E-4|
|2026-06-26T07:02:55.936149Z|408.42430114746094| 408.6743137892853|102.30968156071127|  100.0| -1.1444091796875E-4|
|2026-06-26T07:02:55.936649Z|408.47442626953125|408.72431378928536|102.21161311213572|  100.0|  -2.288818359375E-4|
|2026-06-26T07:02:55.937149Z|408.52455139160156|408.77431378928543|102.11821458968282|  100.0|  1.1444091796875E-4|
|2026-06-26T07:02:55.937648Z| 408.5746765136719| 408.8243137892855|102.02926361591815|  100.0|-9.72747802734375E-4|
|2026-06-26T07:02:55.938148Z| 408.6250305175781|408.87431378928557|101.96634667289824|  100.0|-8.58306884765625E-4|
+---------------------------+------------------+------------------+------------------+-------+--------------------+
Total line number = 10
It costs 0.041s
```

jobとaxis1のビューテーブルを作成することで、二つのテーブルの結合ができるようになります。

``` SQL
IoTDB> select * from viewdb.axis1 join viewdb.job on job.time = axis1.time limit 10
+---------------------------+-------------------+-----------------+----------------------+-------+-------------------+---------------------------+-----------------------+----------------+---------+-------------+--------------+
|                       time|             actpos|           setpos|               actvelo|setvelo|            posdiff|                       time|                subject|       old_state|new_state|job_namespace|        job_id|
+---------------------------+-------------------+-----------------+----------------------+-------+-------------------+---------------------------+-----------------------+----------------+---------+-------------+--------------+
|2026-06-26T07:02:58.187648Z|  863.5443878173828|865.6475247369115|     801.0718204844812|  800.0|0.10431289672851562|2026-06-26T07:02:58.187648Z|          Move velocity|         process|     quit|  /260626/752|/260626/752/29|
|2026-06-26T07:02:58.197646Z|  871.5545654296875|873.6475247369212|     801.8821566036908|  800.0|  0.092010498046875|2026-06-26T07:02:58.197646Z|          Move velocity|            quit|   finish|  /260626/752|/260626/752/29|
|2026-06-26T07:02:58.207649Z|  879.5427703857422| 881.647524736931|     800.0620485503554|  800.0|0.10293960571289062|2026-06-26T07:02:58.207649Z|    800 deg/s 5 seconds|wait_for_process|  process|  /260626/752|/260626/752/30|
|2026-06-26T07:03:04.007646Z|  5187.513427734375|5187.373378851797|-0.0021566342332348595|    0.0|-0.1398468017578125|2026-06-26T07:03:04.007646Z|           Back to home|wait_for_process|  process|  /260626/752|/260626/752/32|
|2026-06-26T07:03:10.047648Z|  -0.12359619140625|              0.0|  -0.39769881037271354|   -0.0|  0.124053955078125|2026-06-26T07:03:10.047648Z|           Back to home|         process|     quit|  /260626/752|/260626/752/32|
|2026-06-26T07:03:10.057648Z|-0.1242828369140625|              0.0|  -0.17174957380431577|   -0.0|      0.12451171875|2026-06-26T07:03:10.057648Z|           Back to home|            quit|   finish|  /260626/752|/260626/752/32|
|2026-06-26T07:03:10.077648Z| -0.124969482421875|              0.0|   -0.0388987947026434|   -0.0|  0.124969482421875|2026-06-26T07:03:10.077648Z|               JOB ROOT|            quit|   finish|  /260626/752|   /260626/752|
|2026-06-26T07:03:10.117648Z|-0.1247406005859375|              0.0| -0.004713688217759382|   -0.0|      0.12451171875|2026-06-26T07:03:10.117648Z|               JOB ROOT|            idle|     init|  /260626/753|   /260626/753|
|2026-06-26T07:03:10.167650Z|-0.1233673095703125|              0.0|   0.04221958591015352|   -0.0| 0.1238250732421875|2026-06-26T07:03:10.167650Z|Move -20 deg, 200 deg/s|          finish|     init|  /260626/753| /260626/753/3|
|2026-06-26T07:03:10.187646Z|-0.1229095458984375|              0.0|  0.030373440217192564|   -0.0| 0.1229095458984375|2026-06-26T07:03:10.187646Z|Move -20 deg, 200 deg/s|          finish|     init|  /260626/753| /260626/753/5|
+---------------------------+-------------------+-----------------+----------------------+-------+-------------------+---------------------------+-----------------------+----------------+---------+-------------+--------------+
Total line number = 10
It costs 0.136s
```

また、ジョブフレームワークの記録データは、状態変更のイベントが記録される仕様です。実処理は個々の`job_id`が`process`という処理状態の間になりますので、その開始終了時間を抽出するクエリは以下の通りとなります。

``` SQL
IoTDB> select 
    FIRST(subject) as job_name, 
    FIRST(job_id) as job_id, 
    FIRST(job_namespace) as sequence_id, 
    MIN(time) as job_start, 
    MAX(time) as job_end, 
from ( 
    select * 
    from viewdb.job 
    where new_state='process' or old_state='process' 
    ) 
GROUP BY job_id limit 10;
+-----------------------+---------------+-----------+---------------------------+---------------------------+
|               job_name|         job_id|sequence_id|                  job_start|                    job_end|
+-----------------------+---------------+-----------+---------------------------+---------------------------+
|    100 deg/s 5 seconds| /260626/752/28|/260626/752|2026-06-26T07:02:56.317648Z|2026-06-26T07:02:57.517648Z|
|          Move velocity| /260626/752/29|/260626/752|2026-06-26T07:02:57.537644Z|2026-06-26T07:02:58.187648Z|
|    800 deg/s 5 seconds| /260626/752/30|/260626/752|2026-06-26T07:02:58.207649Z|2026-06-26T07:03:03.217649Z|
|                   STOP| /260626/752/31|/260626/752|2026-06-26T07:03:03.237651Z|2026-06-26T07:03:03.987648Z|
|           Back to home| /260626/752/32|/260626/752|2026-06-26T07:03:04.007646Z|2026-06-26T07:03:10.047648Z|
|               JOB ROOT|    /260626/752|/260626/752|2026-06-26T07:03:10.067646Z|2026-06-26T07:03:10.067646Z|
|               JOB ROOT|    /260626/753|/260626/753|2026-06-26T07:03:10.137648Z|2026-06-26T07:03:43.477644Z|
|            STEP MOVING|  /260626/753/1|/260626/753|2026-06-26T07:03:10.657646Z|2026-06-26T07:03:12.517646Z|
|Move +20 deg, 200 deg/s|/260626/753/1/1|/260626/753|2026-06-26T07:03:10.687648Z|2026-06-26T07:03:10.697648Z|
|             Wait 100ms|/260626/753/1/2|/260626/753|2026-06-26T07:03:10.717649Z|2026-06-26T07:03:10.757648Z|
+-----------------------+---------------+-----------+---------------------------+---------------------------+
Total line number = 10
It costs 0.993s
```

さらに拡張して、モータ軸のデータaxis1と結合します。JOB ID毎のモータの位置偏差（位置指令を行った結果のエンコーダによる実位置の差）のジョブ毎の平均値を求めるクエリです。full joinでJOBとAxis1のカラムを結合し、FILL METHOD PREVIOUS でお互いにデータが欠落した箇所を最新の値で埋めます。

これによってすべてのモーションデータに対してJOB_IDが埋められましたので、JOB_IDでグループ化した平均値を集計します。

これを開始、終了時刻と共に一覧するクエリです。

``` SQL
IoTDB> select 
    MIN(time) as start_time,
    MAX(time) as finish_time,
    first(job_id) as job_id, 
    first(job_namespace) as job_namespace, 
    first(subject) as subject,
    avg(posdiff) as average_pos_diff
from (
    select 
        axis1.time,
        job.job_id, 
        job.job_namespace, 
        job.subject,
        job.old_state,
        job.new_state,
        axis1.posdiff
    from 
        viewdb.axis1 
    full join
        viewdb.job on axis1.time = job.time
    FILL METHOD PREVIOUS
    limit 30000
    )
WHERE old_state = 'process' or new_state = 'process'
GROUP BY job_id
+---------------------------+---------------------------+---------------+-------------+-----------------------+---------------------+
|                 start_time|                finish_time|         job_id|job_namespace|                subject|     average_pos_diff|
+---------------------------+---------------------------+---------------+-------------+-----------------------+---------------------+
|2026-06-26T07:02:55.983149Z|2026-06-26T07:02:57.527647Z| /260626/752/28|  /260626/752|    100 deg/s 5 seconds|-0.007465561824058419|
|2026-06-26T07:02:57.537148Z|2026-06-26T07:02:58.197148Z| /260626/752/29|  /260626/752|          Move velocity|  0.08131819904798093|
|2026-06-26T07:02:58.207649Z|2026-06-26T07:03:03.227149Z| /260626/752/30|  /260626/752|    800 deg/s 5 seconds|  0.00913228495711528|
|2026-06-26T07:03:03.237646Z|2026-06-26T07:03:03.997648Z| /260626/752/31|  /260626/752|                   STOP| -0.08382165635618995|
|2026-06-26T07:03:04.007646Z|2026-06-26T07:03:10.057148Z| /260626/752/32|  /260626/752|           Back to home| -0.04866401893048247|
|2026-06-26T07:03:10.067147Z|2026-06-26T07:03:10.077149Z|    /260626/752|  /260626/752|               JOB ROOT|  0.12495858328683036|
|2026-06-26T07:03:10.137148Z|2026-06-26T07:03:10.147648Z|    /260626/753|  /260626/753|               JOB ROOT|  0.12414758855646307|
|2026-06-26T07:03:10.657148Z|2026-06-26T07:03:10.667648Z|  /260626/753/1|  /260626/753|            STEP MOVING|  0.10833913629705255|
|2026-06-26T07:03:10.687648Z|2026-06-26T07:03:10.707146Z|/260626/753/1/1|  /260626/753|Move +20 deg, 200 deg/s|  0.10030746459960938|
|2026-06-26T07:03:10.717648Z|2026-06-26T07:03:10.767148Z|/260626/753/1/2|  /260626/753|             Wait 100ms|   0.0921661376953125|
|2026-06-26T07:03:10.777646Z|2026-06-26T07:03:11.217146Z|/260626/753/1/3|  /260626/753|Move +20 deg, 200 deg/s|  0.10224594566527073|
|2026-06-26T07:03:11.227646Z|2026-06-26T07:03:11.347648Z|/260626/753/1/4|  /260626/753|             Wait 100ms| -0.02168749974778861|
|2026-06-26T07:03:11.357646Z|2026-06-26T07:03:11.797148Z|/260626/753/1/5|  /260626/753|Move +20 deg, 200 deg/s| 0.048424178903753105|
|2026-06-26T07:03:11.807646Z|2026-06-26T07:03:11.927149Z|/260626/753/1/6|  /260626/753|             Wait 100ms|-0.043470453919216806|
|2026-06-26T07:03:11.937646Z|2026-06-26T07:03:12.377646Z|/260626/753/1/7|  /260626/753|Move +20 deg, 200 deg/s| 0.030721417900656356|
+---------------------------+---------------------------+---------------+-------------+-----------------------+---------------------+
Total line number = 15
It costs 0.052s
```

さらにこれをサブクエリとし、特定のジョブ名称だけに限定すると、同じ動作に対する位置偏差の発生傾向が一覧できます。


``` SQL
select * FROM(
    select 
        MIN(time) as start_time,
        MAX(time) as finish_time,
        first(job_id) as job_id, 
        first(job_namespace) as job_namespace, 
        first(subject) as subject,
        avg(posdiff) as average_pos_diff
    from (
        select 
            axis1.time,
            job.job_id, 
            job.job_namespace, 
            job.subject,
            job.old_state,
            job.new_state,
            axis1.posdiff
        from 
            viewdb.axis1 
        full join
            viewdb.job on axis1.time = job.time
        FILL METHOD PREVIOUS
        limit 30000
        )
    WHERE old_state = 'process' or new_state = 'process'
    GROUP BY job_id
) WHERE subject = 'Move +20 deg, 200 deg/s';
+---------------------------+---------------------------+---------------+-------------+-----------------------+--------------------+
|                 start_time|                finish_time|         job_id|job_namespace|                subject|    average_pos_diff|
+---------------------------+---------------------------+---------------+-------------+-----------------------+--------------------+
|2026-06-26T07:03:10.687648Z|2026-06-26T07:03:10.707146Z|/260626/753/1/1|  /260626/753|Move +20 deg, 200 deg/s| 0.10030746459960938|
|2026-06-26T07:03:10.777646Z|2026-06-26T07:03:11.217146Z|/260626/753/1/3|  /260626/753|Move +20 deg, 200 deg/s| 0.10224594566527073|
|2026-06-26T07:03:11.357646Z|2026-06-26T07:03:11.797148Z|/260626/753/1/5|  /260626/753|Move +20 deg, 200 deg/s|0.048424178903753105|
|2026-06-26T07:03:11.937646Z|2026-06-26T07:03:12.377646Z|/260626/753/1/7|  /260626/753|Move +20 deg, 200 deg/s|0.030721417900656356|
|2026-06-26T07:03:44.097148Z|2026-06-26T07:03:44.117149Z|/260626/754/1/1|  /260626/754|Move +20 deg, 200 deg/s| 0.10132653372628349|
|2026-06-26T07:03:44.187649Z|2026-06-26T07:03:44.627146Z|/260626/754/1/3|  /260626/754|Move +20 deg, 200 deg/s| 0.10183260741217588|
|2026-06-26T07:03:44.767648Z|2026-06-26T07:03:45.207646Z|/260626/754/1/5|  /260626/754|Move +20 deg, 200 deg/s| 0.04758722259833242|
|2026-06-26T07:03:45.347146Z|2026-06-26T07:03:45.787148Z|/260626/754/1/7|  /260626/754|Move +20 deg, 200 deg/s|0.030995388420260683|
|2026-06-26T07:04:17.507148Z|2026-06-26T07:04:17.527647Z|/260626/755/1/1|  /260626/755|Move +20 deg, 200 deg/s|  0.1024491446358817|
|2026-06-26T07:04:17.597146Z|2026-06-26T07:04:18.037646Z|/260626/755/1/3|  /260626/755|Move +20 deg, 200 deg/s| 0.10193925211680704|
|2026-06-26T07:04:18.177648Z|2026-06-26T07:04:18.617149Z|/260626/755/1/5|  /260626/755|Move +20 deg, 200 deg/s| 0.04854210930433501|
|2026-06-26T07:04:18.757648Z|2026-06-26T07:04:19.197150Z|/260626/755/1/7|  /260626/755|Move +20 deg, 200 deg/s|0.031245166605169124|
|2026-06-26T07:04:50.917648Z|2026-06-26T07:04:50.937148Z|/260626/756/1/1|  /260626/756|Move +20 deg, 200 deg/s| 0.09794998168945312|
|2026-06-26T07:04:51.007646Z|2026-06-26T07:04:51.447146Z|/260626/756/1/3|  /260626/756|Move +20 deg, 200 deg/s| 0.10126137706397205|
|2026-06-26T07:04:51.587149Z|2026-06-26T07:04:52.027148Z|/260626/756/1/5|  /260626/756|Move +20 deg, 200 deg/s|0.048468194040311434|
|2026-06-26T07:04:52.167648Z|2026-06-26T07:04:52.607648Z|/260626/756/1/7|  /260626/756|Move +20 deg, 200 deg/s| 0.03167645460894319|
|2026-06-26T07:05:24.327147Z|2026-06-26T07:05:24.347148Z|/260626/757/1/1|  /260626/757|Move +20 deg, 200 deg/s| 0.10129383632114955|
|2026-06-26T07:05:24.417148Z|2026-06-26T07:05:24.857148Z|/260626/757/1/3|  /260626/757|Move +20 deg, 200 deg/s|  0.1020650798771657|
|2026-06-26T07:05:24.997148Z|2026-06-26T07:05:25.437648Z|/260626/757/1/5|  /260626/757|Move +20 deg, 200 deg/s|0.047608977130963334|
|2026-06-26T07:05:25.577147Z|2026-06-26T07:05:26.017148Z|/260626/757/1/7|  /260626/757|Move +20 deg, 200 deg/s|0.030587355476232175|
+---------------------------+---------------------------+---------------+-------------+-----------------------+--------------------+
Total line number = 20
It costs 0.315s
```

このように、記録したデータをテーブルモードで使えるようにすることで、SQLによる豊富な分析が行えるようになります。

もちろん、ツリーモードのままでAPIを使ってメモリ上で処理することも可能ですが、最後の例のように3万件ものモーションのサイクルデータを取り扱うには、データ転送だけでも大きなコストになります。クエリで取り扱えることに大きなメリットがあると言えるでしょう。