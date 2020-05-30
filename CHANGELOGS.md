2020-05-30 (0.7.5)
========================
* Dynamic Follow 更新至 ShaneSmiskol:stock_additions 0.7.5 版。(感謝 @ShaneSmiskol 提供代碼、 @Wei 測試)
* Updated Dynamic Follow to ShaneSmiskol:stock_additions 0.7.5. (Special Thanks to @ShaneSmiskol for the feature and @Wei for testing)

2020-05-28 (0.7.5)
========================
* 優化 Lexus GSH 轉向。(感謝 @簡銘佑 測試)
* Optimize Lexus GSH steering. (Thanks to @簡銘佑)
* C2 支援自動關機「DragonAutoShutdownAt」參數。(感謝 @cgw1968 建議)
* C2 to support auto shutdown "DragonAutoShutDownAt" param. (Thanks to @cgw1968)
* 修正出現「pedalPressed」的錯誤。(感謝 @Wei 回報)
* Fixed issue showing "pedalPressed" error. (Thanks to @Wei) 

2020-05-26 (0.7.5)
========================
* 將剎車狀熊顯示於 dp 資訊欄。
* Added brake indicator to dp infobar.
* 修正「溫度監控」燈示。
* Fixed "Temp monitor" indicator.
* 加入「方向燈取消控制」延遲控制設。(感謝 @wabes 建議)
* Added delay config to "Disable Lat Control on Blinker". (Thanks to @wabes)
* 加入巴西版 2020 Corolla Hybrid 指紋v2。(感謝 @berno22 提供)
* Added Brazil 2020 Corolla Hybrid FPv2. (Thanks to @berno22) 

2020-05-25 (0.7.5)
========================
* 加入對 VW MQB/PQ 的支援。(感謝 @dingliangxue 移植)
* Added support to VW MQB/PQ platform. (Thanks to @dingliangxue)

2020-05-21 (0.7.5)
========================
* 修改成 3 小時後停止供電。(感謝 @Wei 建議)
* Updated to stop charging after 3 hrs. (Thanks to @Wei)
* 移除行車記錄下的「碰撞偵測」功能。
* Removed Impact Detection in Dashcam.
* 修正開啟「Noctua 風扇」模式導致的錯誤。(感謝 @阿濤 回報)
* Fixed a bug caused by enabling "Noctua Mod". (Thanks to @阿濤)
* 修正「位智模式」無法顯示警示的問題。(感謝 @axandres 回報)
* Fixed alert issue in waze mode. (Thanks to @axandres)
* 修正無法顯示更新中圖示的問題。
* Fixed unable to display "UPDATING" icon issue. 

2020-05-20 (0.7.5)
========================
* 加入「允許多次自動換道」功能。(感謝 @阿濤 建議)
* Added "Allow Continuous Auto Lane Change" Toggle. (Thanks to @阿濤)
* 修正開機後設定頁面有時會錯誤的問題。(感謝 @salmankhan、@Wei 回報)
* Fixed setting page crash issue. (Thanks to @salmankhan, @Wei)
* 修正熄火後一直出現更新訊息的錯誤。(感謝 @Sky Chang 回報)
* Fixed issue that keep showing update prompt. (Thanks to @Sky Chang)

2020-05-19 (0.7.5)
========================
* 加入 DragonEnableAutoUpdate 預設值。
* Added DragonEnableAutoUpdate default value.

2020-05-18 (0.7.5)
========================
* 修正因同時使用「社群功能」和「自定車型」造成的加減速問題。(特別感謝 @Wei、@Sky Chang、@Han9365、@鄧育林 的測試以及回報。)
* Fixed acceleration issue caused by used of both "Community Maintain Feature" and "Custom Car Model"

2020-05-16 (0.7.5)
========================
* 新增 DragonMaxSpeedLimit 設定值 (mph)，當如果車速高於此值 op 將會停止操控。(感謝 @Anthony 建議)
* Added DragonMaxSpeedLimit parameter (mph), op will stop controlling when car speed is high than the value. (Thanks to @Anthony)
* 更新 appd 使用 cnpmjs 來下載 APKs。
* Updated appd to use cnpmjs to download APKs.
* 修正更新服務。(感謝 @Wei)
* Fixed Update Service. (Thanks to @Wei)
* 新增加拿大版 2018 Toyota Sienna LTD 指紋(v2)。(感謝 明峰 提供)
* Added Canada 2018 Toyota Sienna LTD fingerprint (v2). (Thanks to 明峰)

2020-05-15 (0.7.5)
========================
* 新增「通過移動網路上傳」開關
* Added Upload Over Mobile Network toggle.
* 新增「通過熱點上傳」開關
* Added Upload Over Hotspot toggle.
* 新增加拿大版 2018 Toyota Sienna LTD 指紋(v1)。(感謝 明峰 提供)
* Added Canada 2018 Toyota Sienna LTD fingerprint (v1). (Thanks to 明峰)
* 新增大陸版 Volkswagen Golf GTI 指紋 (v1)。(感謝 easyeiji 提供)
* Added China Volkswagen Golf GTI fingerprint (v1). (Thanks to easyeiji)

2020-05-10
========================
* 基於最新 openpilot 0.7.5 devel-staging.
* Based on latest openpilot 0.7.5 devel-staging.
* 更新 dp 圖示 (特別感謝 @wabes 的設計與提供)。
* Updated dp logo, special thanks to @wabes for the design.
* 簡/繁中文版和 i18n 整合成為單一版本。  
* Merged zhs/zht/i18n versions into one.
* 新增大陸版 CAMRY HYBRID 指紋v2。(感謝 @杜子腾)
* Added China Camry Hybrid FPv2. (Thanks to @杜子腾) 
* 新增台灣版 Altis HYBRID 指紋v1。(感謝 @Fish)
* Added Taiwan Altis Hybrid FPv1. (Thanks to @Fish)
* 新增行駛時關閉畫面功能。
* Added Screen off while driving feature.
* 新增倒車時關閉畫面功能。
* Added Screen off while reversing feature.
* 新增駕駛介面加入「加速模式」切換鈕。 
* Added acceleration profile toggle onto driving UI.
* 新增自定車型功能，取代指紋暫存功能。
* Replaced fingerprint cache with custom car model selector.
* 新增可調亮度。
* Added Brightness changer.
* 新增部分德語支持。(特別感謝 @arne182 提供)
* Added partial de_DE language support (Thanks to @arne182)
* 新增停車碰撞偵測記錄功能。
* Added off road impact detection to dashcam.