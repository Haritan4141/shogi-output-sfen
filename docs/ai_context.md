# AI Context

このファイルは、VSCode再起動・AI拡張機能再起動・新規チャット開始後に、次のAIエージェントが迷わず作業を再開するための引き継ぎメモです。重要な進捗、設計判断、検証結果、未完了タスクが増えたら必ず更新してください。

## プロジェクト概要

このプロジェクトは、将棋アプリのPNG/JPEGスクリーンショットから盤面と持ち駒を認識し、SFEN形式を標準出力するPythonツールです。CPU対戦や棋譜研究で、画面上の局面を将棋エンジンへ渡しやすくすることを目的にしています。

主な技術スタック:
- Python
- OpenCV (`opencv-python`)
- NumPy
- PyYAML
- unittest

基本実行:

```powershell
pip install -r requirements.txt
python shogi_sfen_reader.py input.png --config config.yaml --turn b
python shogi_sfen_reader.py "kihu_tests\スクリーンショット 2026-05-21 140042.png" --config config_taikyoku.yaml --turn b
```

デバッグ・切り出し:

```powershell
python shogi_sfen_reader.py input.png --config config.yaml --turn b --debug
python shogi_sfen_reader.py input.png --config config.yaml --turn b --save-cells out/cells --save-hands out/hands
```

テスト:

```powershell
python -m unittest discover -s tests
```

## 現在の作業目的

現在の目的は、棋譜テキストとスクリーンショットのペアを増やし、画像認識SFENが棋譜から復元した局面と一致するか継続検証することです。加えて、`shogi-auto-cpu` から ADB raw screenshot 用の SFEN 認識ライブラリとして利用できるように、`config_adb.yaml` と ADB 由来テンプレートを整備しています。

現状:
- 2026-05-19追加分10盤面と2026-05-21 13時台追加分10盤面は `kihu_tests/確認済/` に移動済み。
- 2026-05-21 14時台追加分10盤面は `kihu_tests/` 直下に配置。
- 合計30盤面を `tests/kifu_positions.yaml` に登録済み。
- 30盤面すべてで、盤面・持ち駒が棋譜復元SFENと一致。
- `python -m unittest discover -s tests` で30盤面を含む回帰テストを実行できる。
- `shogi-auto-cpu` から Git submodule として参照されている。
- `config_adb.yaml` は `1080x2400` の `adb exec-out screencap -p` 画像を前提にした設定。

変更対象の範囲:
- `templates/pieces/`
- `templates/hand_digits/`
- `tests/kifu_positions.yaml`
- 必要に応じて `src/` 配下の認識処理
- この引き継ぎファイル

## これまでに実施した作業

主な実装済み機能:
- `shogi_sfen_reader.py` をCLI入口として実装。
- `config.yaml` / `config_taikyoku.yaml` で盤面座標、持ち駒領域、スロット、閾値を指定。
- `config_adb.yaml` で ADB raw screenshot 用の盤面座標、持ち駒領域、スロット、閾値を指定。
- `src/board_detector.py` で盤面切り出し。
- `src/cell_extractor.py` で9x9セル切り出し。
- `src/piece_recognizer.py` で駒・成駒・空マスのテンプレートマッチング認識。
- `src/hand_detector.py` / `src/hand_recognizer.py` で先手・後手の持ち駒と枚数を認識。
- `src/sfen.py` で内部表現をSFENへ変換。
- `--debug`, `--save-cells`, `--save-hands` に対応。
- `src/csa.py` でCSA/Shogi Quest形式の棋譜テキストを指定手数まで再生し、SFEN化できるようにした。
- `tests/expected_positions.yaml` / `tests/test_expected_positions.py` で既知SFENとの比較テストを追加。
- `tests/kifu_positions.yaml` / `tests/test_kifu_positions.py` で棋譜復元局面との比較テストを追加。

採用した方針:
- 盤面位置は自動検出せず、config指定の固定座標を使う。
- 初期認識器はテンプレートマッチング方式。
- 先手・後手、成駒は別テンプレートとして扱う。
- 持ち駒の数字は `templates/hand_digits/<数値>/...png` のテンプレートマッチングで認識する。
- 数字領域に赤い数字が見えない場合は、枚数表示なしとして1枚扱いにする。
- 認識不能なセルや持ち駒がある場合はSFENを無理に出さずエラーにする。

直近までの修正・検証:
- 相手持ち駒の数字が表示されていないのに、背景や駒の一部を数字として誤認識する問題を修正。
  - `src/hand_recognizer.py` の `_recognize_count()` で、数字テンプレート照合前に `_looks_blank()` を通し、赤い数字がない場合は1枚扱いにする。
- 2026-05-19追加分10盤面を検証。
  - 初回は6件一致、4件不一致。
  - 不一致原因:
    - `184419`: 後手龍を後手馬として誤認識。
    - `184509`: 後手成桂を後手成銀として誤認識。
    - `184548`: 後手持ち駒の桂3枚を2枚として誤認識。
    - `184834`: 後手持ち駒の歩7枚を2枚として誤認識。
  - 追加テンプレート:
    - `templates/pieces/w_+R/kihu_184419_r8c3.png`
    - `templates/pieces/w_+N/kihu_184509_r7c3.png`
    - `templates/hand_digits/3/kihu_184548_w_N.png`
    - `templates/hand_digits/7/kihu_184834_w_P.png`
- 2026-05-21 13時台追加分10盤面を検証。
  - 初回は7件一致、3件不一致。
  - 不一致原因はすべて後手龍 `w_+R` を後手馬 `w_+B` と読む誤認識。
  - 追加テンプレート:
    - `templates/pieces/w_+R/kihu_134315_r8c4.png`
    - `templates/pieces/w_+R/kihu_134340_r8c7.png`
    - `templates/pieces/w_+R/kihu_134438_r8c8.png`
- 2026-05-21 14時台追加分10盤面を検証。
  - 初回は5件一致、5件不一致。
  - 不一致原因:
    - `140042`: 後手龍を後手馬として誤認識。
    - `140111`: 後手龍を後手馬として誤認識。
    - `140346`: 先手成桂を先手成銀として誤認識。
    - `140431`: 後手龍を後手馬として誤認識。
    - `140458`: 後手龍を後手馬として誤認識。
  - 追加テンプレート:
    - `templates/pieces/w_+R/kihu_140042_r9c1.png`
    - `templates/pieces/w_+R/kihu_140111_r9c6.png`
    - `templates/pieces/b_+N/kihu_140346_r1c7.png`
    - `templates/pieces/w_+R/kihu_140431_r9c4.png`
    - `templates/pieces/w_+R/kihu_140458_r9c4.png`
- 追加後、合計30件すべてが棋譜復元局面と一致。
- `tests/kifu_positions.yaml` を合計30件に更新。
- 2026-05-22/23 の `shogi-auto-cpu` 自動対局検証で、ADB raw screenshot 向けの追加を実施。
  - `config_adb.yaml` を追加。
  - `src/piece_recognizer.py` でテンプレート照合をベクトル化し、空マス fallback を追加。
  - 追加テンプレート:
    - `templates/pieces/b_+P/promoted_pawn_low_score_r3c7.png`
    - `templates/pieces/b_R/black_gold_hand_2_after_rook_capture_b_R_hand.png`
    - `templates/pieces/w_B/white_bishop_hand_2_w_B_hand.png`
    - `templates/pieces/w_R/white_rook_hand_after_capture_w_R_hand.png`
    - `templates/hand_digits/2/black_gold_hand_2_after_rook_capture_b_G.png`
    - `templates/hand_digits/2/white_bishop_hand_2_w_B.png`
    - `templates/hand_digits/2/white_gold_hand_2_after_gold_capture_w_G.png`
    - `templates/hand_digits/4/black_pawn_hand_4_b_P.png`
  - commit `7e32fb0 Improve ADB screenshot recognition` として `main` に push 済み。

## 未完了タスク

残っている作業:
- 新しいスクリーンショットで不明セルや持ち駒誤認識が出た場合、`--debug` の切り出しを確認し、正しいラベルのテンプレートへ追加する。
- 持ち駒数字 `9`, `11` から `18` は実戦上ほぼ不要という判断で保留中。
- 手番の自動認識は後回し。現状はCLIの `--turn b` / `--turn w` 指定。
- scrcpyからのリアルタイムキャプチャは未実装。
- 盤面上端の自動検出は現状 `shogi-auto-cpu` 側で実装済み。このライブラリ本体へ移植する場合も、既存の固定座標config方式は残す。

既知の注意点:
- 後手龍 `w_+R` と後手馬 `w_+B` の混同が最も繰り返し出ている。赤い成駒文字が似ており、スコア差が小さいため閾値では弾きにくい。
- 後手成桂 `w_+N` と後手成銀 `w_+S`、先手成桂 `b_+N` と先手成銀 `b_+S` も混同実績あり。
- 相手持ち駒の小さい赤数字は `2`, `3`, `7` などで混同実績あり。
- OpenCVの通常 `imread` は日本語パスで失敗しやすい。プロジェクト内では `src/image_io.py` の読み書きを使う。
- `out/` はデバッグ生成物であり、基本的に成果物ではない。

## 動作確認・検証状況

30盤面の棋譜照合結果:

2026-05-19確認済:
- `184324`: move 82, turn `b`
- `184419`: move 131, turn `w`
- `184509`: move 84, turn `b`
- `184548`: move 114, turn `b`
- `184700`: move 125, turn `w`
- `184740`: move 53, turn `w`
- `184811`: move 69, turn `w`
- `184834`: move 125, turn `w`
- `184856`: move 110, turn `b`
- `184922`: move 120, turn `b`

2026-05-21 13時台確認済:
- `134051`: move 96, turn `b`
- `134125`: move 55, turn `w`
- `134155`: move 109, turn `w`
- `134224`: move 82, turn `b`
- `134252`: move 71, turn `w`
- `134315`: move 116, turn `b`
- `134340`: move 139, turn `w`
- `134408`: move 111, turn `w`
- `134438`: move 107, turn `w`
- `134508`: move 137, turn `w`

2026-05-21 14時台追加:
- `140042`: move 109, turn `w`
- `140111`: move 113, turn `w`
- `140222`: move 130, turn `b`
- `140247`: move 112, turn `b`
- `140311`: move 97, turn `w`
- `140346`: move 107, turn `w`
- `140407`: move 151, turn `w`
- `140431`: move 129, turn `w`
- `140458`: move 115, turn `w`
- `140520`: move 132, turn `b`

確認できたこと:
- 上記30件は、テンプレート追加後に盤面・持ち駒が棋譜復元SFENと一致。
- 手番は画像からは読まず、棋譜テストでは棋譜復元SFENの手番をCLIへ渡す。
- 累計30件中、各追加バッチの初回一致は18件。残り12件はテンプレート追加で一致。
- 誤認識の中心は後手龍 `w_+R` と後手馬 `w_+B` の混同。持ち駒は直近20件では追加修正なし。

全テスト:

```powershell
python -m unittest discover -s tests
```

結果:

```text
Ran 9 tests in 69.500s
OK
```

まだ確認できていないこと:
- リアルタイムキャプチャ、手番自動認識、複数アプリ対応。
- さらに別日の局面・別表示条件での安定性。
- ADB raw screenshot 用 `config_adb.yaml` の別解像度・別端末での安定性。

## 重要なファイル・ディレクトリ

- `README.md`: ユーザー向け説明。`config_adb.yaml`、ADB raw screenshot、`shogi-auto-cpu` からの利用も記載。
- `docs/ai_context.md`: AI作業引き継ぎ用。このファイル。
- `shogi_sfen_reader.py`: CLI入口。
- `src/`: 実装本体。
- `src/csa.py`: CSA/Shogi Quest形式の棋譜を再生し、局面をSFEN化する軽量パーサ。
- `tests/expected_positions.yaml`: 既知SFENとの回帰テストデータ。
- `tests/kifu_positions.yaml`: 棋譜テキストとスクリーンショットのペアから正確性を検証するテストデータ。現在30件。
- `config.yaml`: 通常画面用設定。
- `config_taikyoku.yaml`: 観戦・再生画面用設定。
- `config_adb.yaml`: ADB raw screenshot 用設定。現状は `1080x2400` 前提。
- `templates/pieces/`: 駒テンプレート。
- `templates/hand_digits/`: 持ち駒枚数の数字テンプレート。
- `sample_images/`: サンプル画像。
- `kihu_tests/`: 棋譜テキストとスクリーンショットの正確性テスト用データ。
- `kihu_tests/確認済/`: 検証済みペアの退避先。
- `out/`: デバッグ出力。`.gitignore` 対象。
- `engines/`: 将棋エンジン。現状の画像認識テストでは未使用。

## 注意事項・制約

- 既存仕様を壊さないこと。
- 固定座標config方式が前提。自動盤面検出へ変更する場合も、既存のconfig方式は残すこと。
- 影響範囲が大きい変更は、理由と影響範囲を明確にすること。
- ユーザーが作成・変更したファイルを勝手に上書きしないこと。
- 自分が変更していない差分を勝手に修正・削除しないこと。
- 不明点がある場合は、推測で大きく進めず、必要に応じて確認すること。
- テンプレート追加時は、誤ラベル混入を最も警戒すること。
- 閾値を下げる場合は、誤認識が増えないか複数サンプルで検証すること。
- 日本語ファイル名が多いため、パス処理とエンコーディングに注意すること。

## Git 操作に関する厳守事項

危険なGit操作は絶対に行わないこと。

特に以下は禁止:
- `git reset`
- `git reset --hard`
- `git clean`
- `git checkout -- .`
- `git restore .`
- `git push --force`
- `git push -f`
- `git rebase`
- 履歴を書き換える操作
- ユーザーの許可なくファイルを削除する操作

コミット、ブランチ作成、push、pull、merge、rebaseなどが必要そうな場合は、実行前に必ずユーザーに確認すること。既存の変更を勝手に破棄しないこと。Git操作を提案する場合は、実行内容とリスクを説明すること。

## 運用ルール

- 重要な進捗があったら `docs/ai_context.md` を随時更新すること。
- 方針変更、重要な実装完了、問題の発見、未完了タスクの追加・解決があった場合は必ず追記すること。
- 作業を中断する前、または一段落したタイミングで、最新状況を反映すること。
- 次回セッションのAIエージェントがこのファイルを最初に読む前提で、簡潔かつ具体的に書くこと。
- READMEはユーザー向け、`docs/ai_context.md` は作業引き継ぎ向けとして使い分けること。
- 正解SFENが分かっている局面は `tests/expected_positions.yaml` に追加する。
- CSA棋譜がある局面は `tests/kifu_positions.yaml` に追加する。棋譜がスクリーンショットより先の手まで含む場合は、画面下部の手数を `move_number` に指定する。

## 更新履歴

- 2026-05-19: `docs/ai_context.md` を作成。プロジェクト概要、実装履歴、注意事項、Git禁止事項、運用ルールを記録。
- 2026-05-19: 相手持ち駒の数字誤認識を修正。数字が表示されていない領域を1枚扱いにする処理と回帰テストを追加。
- 2026-05-19: CSA/Shogi Quest形式の棋譜パーサ `src/csa.py` と棋譜ベースの局面テストを追加。
- 2026-05-19: `kihu_tests/` の10盤面を検証。4件の誤認識に対して駒テンプレート2件、数字テンプレート2件を追加し、10件すべてで棋譜復元局面との一致を確認。
- 2026-05-19: `python -m unittest discover -s tests` を実行し、`Ran 9 tests`, `OK` を確認。
- 2026-05-21: 既存の検証済み10盤面が `kihu_tests/確認済/` に移動されたため、`tests/kifu_positions.yaml` のパスを更新。
- 2026-05-21: 13時台の新規10盤面を検証。初回7件一致、3件は `w_+R` を `w_+B` と読む誤認識。`w_+R` テンプレート3件を追加し、10件すべて一致。
- 2026-05-21: `tests/kifu_positions.yaml` を合計20件に更新。`python -m unittest discover -s tests` を実行し、`Ran 9 tests in 46.941s`, `OK` を確認。
- 2026-05-21: 検証済み20盤面が `kihu_tests/確認済/` に移動されたため、`tests/kifu_positions.yaml` のパスを更新。
- 2026-05-21: 14時台の新規10盤面を検証。初回5件一致、4件は `w_+R` を `w_+B` と読む誤認識、1件は `b_+N` を `b_+S` と読む誤認識。`w_+R` テンプレート4件と `b_+N` テンプレート1件を追加し、10件すべて一致。
- 2026-05-21: `tests/kifu_positions.yaml` を合計30件に更新。`python -m unittest discover -s tests` を実行し、`Ran 9 tests in 69.500s`, `OK` を確認。
- 2026-05-23: `shogi-auto-cpu` 連携向けに ADB raw screenshot 対応を整理。`config_adb.yaml`、ADB由来テンプレート、`src/piece_recognizer.py` のベクトル化・空マスfallbackを `7e32fb0 Improve ADB screenshot recognition` として push 済み。
- 2026-05-23: README と `docs/ai_context.md` を更新し、ADB raw screenshot、追加テンプレート、`shogi-auto-cpu` からの submodule 利用を記録。
