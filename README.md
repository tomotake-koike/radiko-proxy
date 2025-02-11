# radiko-proxy
YAMAHAの旧式Networkレシーバ(手前はR-N303)でradiko.jpを視聴するためのProxy（2025/01/20以降対応）

## いきさつ

昨年後半にオークションで購入したNetworkレシーバでradiko.jpを楽しんでいたものの2025/01/20以降突然視聴できなくなった。
YAMAHA曰く他のデバイスで受信してAirPlayなりBluetoothで連携すれば聴けるということだったが、今まで機器単体で聴けていた機能が不全に陥るのは製品仕様として受け入れ難い。

- YAMAHAのお知らせ「[radikoサービスの受信停止について](https://radiko.jp/#!/info/2716)」
- radiko.jpのお知らせ「[一部radiko聴取可能機器でのサポート終了のお知らせ](https://radiko.jp/#!/info/2716)」

巷の情報によるとYAMAHAの機器に限った話しではなく、原因はradiko.jp側がセキュリティ・アップデートのためhttps対応したとのこと。

- TEACのお知らせ「[一部ネットワークオーディオ製品におけるradikoサービスの受信停止について](https://www.teac.co.jp/jp/support/news/7764)

radiko.jp設立目的にもある公共のラジオ配信基盤としての役割からして、平文によるメディアストリームを完全に撤廃したりするとそれはそれで総務省に怒られるでしょうし、恐らく抜け穴があるだろうなと考えた。（機器メーカーはかつての機器におけるファームウェアをサポートし続けることは難しいのは自明なわけで、そう言ったビジネス的な理由と推測。SDGsのジレンマ。）

- 総務省「[デジタル時代における放送制度の在り方に関する検討会（第25回）](https://www.soumu.go.jp/main_sosiki/kenkyu/digital_hososeido/02ryutsu07_04000459.html)」
  - 「[radikoの現状について](https://www.soumu.go.jp/main_content/000941517.pdf)」

## 調査と対処方針

[RFC8216](https://datatracker.ietf.org/doc/html/rfc8216)のHTTP Live Streaming(HLS)ベースなので通信を覗いてみたら、全てがhttpsになっていないしm3u8とかm3uのMedia Playlistの中には（配列の後ろにいるので非優先になっているものの）httpのエンドポイントも残っていることが判明。（そもそもウチの機器はPlaylistsの取得すらhttpsでやっていないし、サーバサイドもサポートしている。）

ということでPlaylistの取得応答をProxyで傍受してhttpのエンドポイントに限定してあげれば、またウチの旧式のYAMAHAネットワークレシーバーでもまたradiko.jpを視聴できるであろうと簡単なPythonスクリプトを執筆。

## radiko-proxy.py

かなりプリミティヴな実装になっているため、dnsmasqとかiptables(もしくはhaproxy)に頼っている。

- 古いシングルボードコンピュータ（かつ[ラズパイもどき](https://akizukidenshi.com/catalog/g/g112301/)）でも動くように実装
  - pipしなくてすむように標準ライブラリのimportだけで書く
    - （XMLのElementTreeが心配だが…）
  - 適当なsocket実装なのでMedis Playlist取得時にsocketインタフェースレベルでバッファ分割すると視聴が失敗する（機器の電源ON/OFF）
- このProxyにradiko.jp宛てのパケットが通るようにローカルDNSサーバ（dnsmaqとかで）を立ててネットワークレシーバー側の名前解決をさせる
  - radiko-proxy.pyからは正規のradiko.jpの名前解決が行えるようこのローカルDNSサーバでresolveさせない
- http://radiko.jp の通信だけ処理するためhttpsのfowardingは別途行う必要がある（iptablesやhaproxyとか）
- **radiko.jpがHLSのMedia Playlistにhttpのエンドポイントを返さなくなったら別策を検討する必要がある**


## 導入手順

### dnsmasq

- `/etc/dnsmasq.conf`サンプル
  ```
  port=53
  domain-needed
  bogus-priv
  no-hosts
  addn-hosts=/etc/hosts.dnsmasq
  user=dnsmasq
  # group=dnsmasq
  bind-interfaces
  listen-address=0.0.0.0
  ```
  
- `/etc/hosts.dnsmasq`サンプル
  ```
  [radiko-proxy.pyを起動するServerのIPaddress] radiko.jp
  ```

### iptablesでhttps://radiko.jpをケア

radiko-proxy.pyを起動するServerで実行。

```sh
sudo sysctl net.ipv4.ip_forward=1
RADIKO_IP=$(nslookup radiko.jp | grep -A 1 Name | grep Address | cut -d \  -f 2 )
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination ${RADIKO_IP}
sudo iptables -t nat -A POSTROUTING -d ${RADIKO_IP} -j MASQUERADE
```

### radiko-proxy.py を実行

適宜daemon化する。
```
sudo python3 radiko-proxy.py
```


## おわりに

いつまでこのスクリプトが通用するか不明ですが、他メーカーの従前ネットワークレシーバー等でも使えると思われ、大勢の方々のradiko.jpライフの一助になれば幸いです。


