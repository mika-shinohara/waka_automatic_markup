import streamlit as st
import pandas as pd
import re
import MeCab
import tempfile
import os

st.title("和歌XML変換ツール（MeCab自動句切れ判定）")
st.write("Excelファイルをアップロードすると、自動で和歌を5・7・5・7・7に分割してXMLを生成します。")

# ファイルアップロードウィジェット
uploaded_file = st.file_uploader("Excelファイル（.xlsx）をアップロードしてください", type=["xlsx"])
sheet_name_input = st.text_input("シート名を入力してください", value="Sheet2")

if uploaded_file is not None:
    if st.button("変換を実行する"):
        # アップロードされたファイルを一時的に保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            # MeCabの初期化
            tagger = MeCab.Tagger()
            
            # Excel読み込み
            df = pd.read_excel(tmp_path, sheet_name=sheet_name_input)
            
            def kanji_to_arabic(s):
                if '|' in s:
                    s = s.split('|')[0]
                m = {'〇':0, '一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9}
                if all(c in m for c in s):
                    return str(int("".join(str(m[c]) for c in s)))
                return s

            def count_moras(kana_str):
                small_kana = "ぁぃぅぇぉゃゅょっっァィゥェォッャュョ"
                count = 0
                for char in kana_str:
                    if char not in small_kana:
                        count += 1
                return count

            def split_waka_by_mecab(waka_body):
                node = tagger.parseToNode(waka_body)
                tokens = []
                while node:
                    surface = node.surface
                    if surface:
                        feature = node.feature.split(',')
                        reading = feature[-1] if len(feature) > 0 and feature[-1] != '*' else surface
                        tokens.append((surface, reading))
                    node = node.next
                    
                target_cumulative = [5, 12, 17, 24, 31]
                clauses = ["", "", "", "", ""]
                current_clause_idx = 0
                current_mora_sum = 0
                
                for surface, reading in tokens:
                    mora_len = count_moras(reading)
                    if current_clause_idx < 4 and current_mora_sum >= target_cumulative[current_clause_idx]:
                        current_clause_idx += 1
                    clauses[current_clause_idx] += surface
                    current_mora_sum += mora_len
                return clauses

            output_xmls = []
            for idx, row in df.iterrows():
                歌集名 = str(row['歌集名']) if pd.notna(row['歌集名']) else ""
                詞書 = row['詞書']
                作者 = row['作者']
                raw_歌 = str(row['歌']) if pd.notna(row['歌']) else ""
                left_note = row['左注']
                
                match = re.match(r'^([〇一二三四五六七八九\|]+)(.*)', raw_歌)
                if not match:
                    continue
                kanji_num = match.group(1)
                waka_body = match.group(2).strip()
                
                arab_num = kanji_to_arabic(kanji_num)
                target_id = f"{歌集名}{arab_num}"
                
                clauses = split_waka_by_mecab(waka_body)
                seg_content = f'<seg style="margin-top: 2em">{clauses[0]}</seg><seg>{clauses[1]}</seg><seg>{clauses[2]}</seg><seg>{clauses[3]}</seg><seg>{clauses[4]}</seg>'
                
                lines = ['<cit>', '                <quote>']
                if pd.notna(詞書) and str(詞書).strip() != "":
                    lines.append(f'                   <lb/><note type="詞書" target="#{target_id}" style="margin-top: 3em">{詞書}</note>')
                if pd.notna(作者) and str(作者).strip() != "":
                    lines.append(f'                   <lb/><note type="作者" target="#{target_id}" style="margin-top: 12em">{作者}</note>')
                lines.append(f'                   <lb/><l n="{arab_num}" xml:id="{target_id}">{seg_content}</l>')
                if pd.notna(left_note) and str(left_note).strip() != "":
                    lines.append(f'                   <lb/><note type="左注" target="#{target_id}" style="margin-top: 5em">{left_note}</note>')
                lines.append('                </quote>')
                lines.append('             </cit>')
                output_xmls.append("\n".join(lines))

            result_text = "\n\n".join(output_xmls)
            st.success("変換が完了しました！")
            st.text_area("出力結果（XML）", result_text, height=300)
            st.download_button(label="結果をTXTファイルとしてダウンロード", data=result_text, file_name="output.xml", mime="text/plain")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)