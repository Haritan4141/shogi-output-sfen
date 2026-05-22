# Shogi Screenshot SFEN Reader

将棋アプリのスクリーンショットから、固定座標で盤面と持ち駒を切り出し、テンプレートマッチングで認識してSFENを標準出力するPythonツールです。初期実装は特定アプリの固定UIを前提にしています。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 使い方

```powershell
python shogi_sfen_reader.py sample_images\初期盤面.png --config config.yaml --turn b
```

`sample_images/対局例/` の観戦・再生画面は盤面と持ち駒の縦位置が通常画面と異なるため、こちらを使います。

```powershell
python shogi_sfen_reader.py "sample_images\対局例\スクリーンショット 2026-05-19 032440.png" --config config_taikyoku.yaml --turn b
```

Android 端末の raw screenshot を ADB で取得して使う場合は、`config_adb.yaml` を使います。この設定は `1080x2400` の `adb exec-out screencap -p` 画像を前提にしています。

```powershell
adb exec-out screencap -p > screen.png
python shogi_sfen_reader.py screen.png --config config_adb.yaml --turn b
```

デバッグ用の切り出しを保存する場合:

```powershell
python shogi_sfen_reader.py input.png --config config.yaml --turn b --debug
python shogi_sfen_reader.py input.png --config config.yaml --turn b --save-cells out/cells --save-hands out/hands
```

認識不能なマスや持ち駒がある場合、SFENは出力せず、どのセルまたは持ち駒スロットが不明かをエラーとして表示します。

## config.yaml

座標はスクリーンショット画像の左上を `(0, 0)` としたピクセル指定です。

```yaml
board:
  top_left: [7, 300]
  width: 570
  height: 621

recognition:
  pieces_dir: templates/pieces
  hand_digits_dir: templates/hand_digits
  piece_threshold: 0.72
  hand_piece_threshold: 0.70
  hand_presence_threshold: 0.45
  digit_threshold: 0.70
  match_size: [64, 64]
  cell_crop_margin: 2
  mode: color

hands:
  black:
    rect: [0, 928, 470, 76]
    relative_to: hand
    slots:
      - piece: P
        rect: [8, 0, 58, 68]
        digit_rect: [47, 40, 28, 30]
```

`hands.black` は先手、`hands.white` は後手です。`relative_to: hand` の場合、各 `slot.rect` と `digit_rect` は持ち駒領域内の相対座標です。`relative_to: screen` にするとスクリーンショット全体の絶対座標として扱います。

## 盤面座標の調べ方

1. `python shogi_sfen_reader.py input.png --config config.yaml --turn b --save-cells out/cells` を実行します。
2. `out/cells/r1c1.png` から `r9c9.png` を確認します。
3. グリッド線が大きく入りすぎる場合は `board.top_left`、`board.width`、`board.height`、`recognition.cell_crop_margin` を調整します。

このリポジトリ内の通常サンプル画像では、盤面は概ね `top_left: [7, 300]`, `width: 570`, `height: 621` です。
`sample_images/対局例/` の観戦・再生画面では `config_taikyoku.yaml` のように `top_left: [7, 288]`, `width: 570`, `height: 621` を使います。

## 持ち駒座標の調べ方

1. `--save-hands out/hands` を指定して実行します。
2. `black_area.png` と `white_area.png` で持ち駒領域の切り出しを確認します。
3. `black_P_piece_*.png` のようなスロット画像を見て、各駒が中央に入るように `slots[].rect` を調整します。
4. 枚数表示があるUIでは `digit_rect` に数字部分だけが入るように指定します。数字表示がない駒は1枚として扱われます。

## 駒テンプレート画像

`templates/pieces/` に以下の名前で配置してください。複数テンプレートを使う場合は、同じラベル名のディレクトリを作って中に画像を入れられます。

```text
templates/pieces/
  empty.png
  b_K.png
  b_R.png
  b_B.png
  b_G.png
  b_S.png
  b_N.png
  b_L.png
  b_P.png
  b_+R.png
  b_+B.png
  b_+S.png
  b_+N.png
  b_+L.png
  b_+P.png
  w_K.png
  ...
```

先手は `b_`、後手は `w_` です。成駒は `b_+P.png` のように `+` を付けます。テンプレートは実際の切り出しセルから作るのが最も安定します。`--save-cells` で保存したセル画像を、余白やグリッド線がなるべく少ない状態でテンプレート化してください。

## 数字テンプレート画像

`templates/hand_digits/` に `0.png` から `18.png` のように配置してください。すべて揃える必要はありませんが、アプリで表示される可能性がある数字は用意してください。複数パターンがある場合は `templates/hand_digits/2/sample1.png` のようなディレクトリ形式も使えます。

## 現在のテンプレート状況

このリポジトリでは、サンプル画像から以下のテンプレートを作成済みです。

- `sample_images/初期盤面.png` 由来: 先手/後手の未成駒、空マス
- `sample_images/持ち駒_自分.png` 由来: 先手の持ち駒 `P/L/N/S/G/B/R`、後手の持ち駒 `P`
- `sample_images/持ち駒複数枚_自分.png` 由来: 後手の持ち駒 `P/L/R`、数字 `2/6/8`
- `sample_images/持ち駒_自分.png` 由来: 数字 `5`
- `sample_images/対局例/` 由来: 盤上の成駒 `+R/+B/+S/+N/+L/+P` の実例、観戦・再生画面の持ち駒、数字 `2/3/4/5/6/7/8/10` の実例
- `sample_images/対局例_追加1/` 由来: 後手馬 `w_+B`、後手竜 `w_+R`、先手成桂 `b_+N`、先手成香 `b_+L`、後手成桂 `w_+N`、後手成香 `w_+L` の実例

現時点のサンプルでは、通常駒、主要な成駒、観戦・再生画面の持ち駒は一通り認識できる状態です。新しいスクリーンショットで不明セルが出た場合は、該当セルを正しいラベルのディレクトリへ追加してください。

ADB raw screenshot で確認した低スコア事例として、以下のテンプレートも追加済みです。

- `templates/pieces/b_+P/promoted_pawn_low_score_r3c7.png`
- `templates/pieces/b_R/black_gold_hand_2_after_rook_capture_b_R_hand.png`
- `templates/pieces/w_B/white_bishop_hand_2_w_B_hand.png`
- `templates/pieces/w_R/white_rook_hand_after_capture_w_R_hand.png`
- `templates/hand_digits/2/black_gold_hand_2_after_rook_capture_b_G.png`
- `templates/hand_digits/2/white_bishop_hand_2_w_B.png`
- `templates/hand_digits/2/white_gold_hand_2_after_gold_capture_w_G.png`
- `templates/hand_digits/4/black_pawn_hand_4_b_P.png`

注意: このアプリでは成銀・成桂・成香が赤い「全」「圭」「杏」のような崩し字で表示されます。似た形を誤ラベルで入れるとSFENが静かに間違うため、追加時はスクリーンショットの手順表示、局面、または手動メモで元の駒種を確認してください。数字は `1` は枚数表示なしとして扱うため不要ですが、`9`、`11` 以上などが画面に出た場合は追加してください。

## デバッグ

`--debug` を指定すると、既定で `out/debug/` に以下を保存します。

- `board.png`: 盤面領域
- `cells/`: 認識前の81マス切り出し
- `cells_recognized/`: 認識ラベルと信頼度付きのセル画像
- `hands/`: 持ち駒領域、各スロット、数字領域
- `recognition.json`: 各セル、各持ち駒スロット、数字認識の信頼度

類似度が閾値未満の場合は不明として扱います。テンプレートを追加した直後は `piece_threshold` や `hand_piece_threshold` をやや低めにし、誤認識が出ない範囲で上げてください。

## 認識処理の注意

`src/piece_recognizer.py` は、読み込み済みテンプレートをベクトル化して一括照合します。テンプレート数が増えても毎セルの照合が極端に遅くなりにくいようにするためです。

また、駒テンプレートの最高スコアが閾値未満でも、セル内に黒画素や赤画素がほとんどない場合は空マスとして扱う fallback があります。これは ADB raw screenshot の空マスが既存テンプレートと低スコアになるケースを吸収するためのものです。駒があるマスを空マス扱いしないよう、閾値を下げる前にデバッグ切り出しで確認してください。

## 複数局面の回帰テスト

盤面・持ち駒の正解SFENが分かっている局面は、`tests/expected_positions.yaml` に追加するとCLI出力と自動比較できます。

```yaml
positions:
  - name: sample_name
    image: sample_images/対局例/example.png
    config: config_taikyoku.yaml
    turn: b
    sfen: 9/9/9/9/9/9/9/9/9 b - 1
```

実行:

```powershell
python -m unittest discover -s tests
```

このテストは「認識できるか」だけでなく、盤上の駒位置、持ち駒の種類、枚数が期待SFENと一致するかを確認します。

ゲーム側からCSA形式の棋譜が出力できる場合は、`tests/kifu_positions.yaml` に画像と棋譜をペアで追加できます。棋譜テキストが最終局面まで含んでいて、スクリーンショットが途中手数の場合は、画面下部に表示されている手数を `move_number` に指定します。

```yaml
positions:
  - name: kihu_sample
    image: kihu_tests/example.png
    kifu: kihu_tests/example.txt
    config: config_taikyoku.yaml
    move_number: 106
    sfen_move_number: 1
```

CSA棋譜は `src/csa.py` で指定手数まで再生し、画像認識のSFENと比較します。

## scrcpyでの利用

対象アプリは `C:\Tools\scrcpy-win64-v3.3.1\scrcpy.exe` でPC画面上に表示する前提です。scrcpyのウィンドウサイズやAndroid側の解像度が変わると座標も変わるため、同じ表示サイズでスクリーンショットを取り、必要に応じて `config.yaml` を調整してください。

将来的なリアルタイム画面キャプチャや手番自動認識は、`src/board_detector.py`、`src/hand_detector.py`、`src/piece_recognizer.py`、`src/hand_recognizer.py` の境界を差し替える形で拡張できます。

## shogi-auto-cpu からの利用

`shogi-auto-cpu` は、このリポジトリを Git submodule として参照します。`shogi-auto-cpu` 側で自動対局を行う場合は、`configs/auto_cpu_adb.json` から `shogi-output-sfen/config_adb.yaml` を使う構成です。

このリポジトリ単体では、画面クリックや将棋エンジン実行は行いません。スクリーンショットからSFENを出力するところまでが責務です。
