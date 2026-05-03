import sys
import unohelper
import officehelper
import json
import urllib.request
import urllib.parse
from com.sun.star.task import XJobExecutor
from com.sun.star.awt import MessageBoxButtons as MSG_BUTTONS
import uno
import os
import logging
import re
import traceback

from com.sun.star.beans import PropertyValue
from com.sun.star.container import XNamed

# UNO 常量 - 不能直接用 com.sun.star.text.ControlCharacter.LINE_BREAK 访问
# 必须通过 uno.getConstantByName 获取
CTRL_LINE_BREAK = 0      # com.sun.star.text.ControlCharacter.LINE_BREAK
CTRL_PARAGRAPH_BREAK = 1 # com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK


def log_to_file(message):
    home_directory = os.path.expanduser('~')
    log_file_path = os.path.join(home_directory, 'translator_log.txt')
    logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(message)s')
    logging.info(message)


def is_chinese(text):
    """检测文本是否主要是中文"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    return chinese_chars > english_chars




def show_message(doc_model, title, message):
    """在 LibreOffice 中弹出消息框"""
    try:
        parent_win = doc_model.CurrentController.getFrame().getContainerWindow()
        toolkit = parent_win.getToolkit()
        msg_box = toolkit.createMessageBox(
            parent_win,
            0,  # MESSAGEBOX
            1,  # BUTTONS_OK
            title,
            message
        )
        msg_box.execute()
        msg_box.dispose()
    except Exception:
        pass


class MainJob(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx
        try:
            self.sm = ctx.getServiceManager()
            self.desktop = XSCRIPTCONTEXT.getDesktop()
            self.document = XSCRIPTCONTEXT.getDocument()
        except NameError:
            self.sm = ctx.ServiceManager
            self.desktop = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)

    def get_config(self, key, default):
        name_file = "localwriter.json"
        path_settings = self.sm.createInstanceWithContext('com.sun.star.util.PathSettings', self.ctx)
        user_config_path = getattr(path_settings, "UserConfig")
        if user_config_path.startswith('file://'):
            user_config_path = str(uno.fileUrlToSystemPath(user_config_path))
        config_file_path = os.path.join(user_config_path, name_file)
        if not os.path.exists(config_file_path):
            return default
        try:
            with open(config_file_path, 'r') as file:
                config_data = json.load(file)
        except (IOError, json.JSONDecodeError):
            return default
        return config_data.get(key, default)

    def set_config(self, key, value):
        name_file = "localwriter.json"
        path_settings = self.sm.createInstanceWithContext('com.sun.star.util.PathSettings', self.ctx)
        user_config_path = getattr(path_settings, "UserConfig")
        if user_config_path.startswith('file://'):
            user_config_path = str(uno.fileUrlToSystemPath(user_config_path))
        config_file_path = os.path.join(user_config_path, name_file)
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r') as file:
                    config_data = json.load(file)
            except (IOError, json.JSONDecodeError):
                config_data = {}
        else:
            config_data = {}
        config_data[key] = value
        try:
            with open(config_file_path, 'w') as file:
                json.dump(config_data, file, indent=4)
        except IOError as e:
            print(f"Error writing to {config_file_path}: {e}")

    def is_translategemma_model(self, model_name):
        """检测是否为 translategemma 系列模型"""
        name_lower = model_name.lower()
        return 'translategemma' in name_lower

    def translate_text(self, source_text):
        """调用 LM Studio API 进行翻译，返回翻译结果字符串"""
        endpoint = self.get_config("endpoint", "http://127.0.0.1:1234")
        model_name = self.get_config("model", "")

        if self.is_translategemma_model(model_name):
            return self._translate_with_completions(endpoint, model_name, source_text)
        else:
            return self._translate_with_chat(endpoint, model_name, source_text)

    def _translate_with_completions(self, endpoint, model_name, source_text):
        """使用 /v1/completions API（适用于 translategemma 等 chat template 不兼容的模型）"""
        url = endpoint.rstrip('/') + "/v1/completions"

        src_lang = "Chinese" if is_chinese(source_text) else "English"
        tgt_lang = "English" if src_lang == "Chinese" else "Chinese"

        # translategemma 需要这种格式才能输出单一翻译结果
        # 格式要点：完整语言名称 + "Output ONLY" + 双重换行分隔
        prompt = (
            "<start_of_turn>user\n"
            "Translate the following " + src_lang + " text into " + tgt_lang + ". "
            "Output ONLY the " + tgt_lang + " translation, no explanations, no alternatives, no options:\n\n"
            + source_text
            + "<end_of_turn>\n"
            "<start_of_turn>model\n"
        )

        data = {
            'prompt': prompt,
            'max_tokens': 4096,
            'temperature': 0.1,
            'stream': False
        }

        if model_name:
            data["model"] = model_name

        json_data = json.dumps(data).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        request = urllib.request.Request(url, data=json_data, headers=headers, method='POST')

        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            raw = result['choices'][0]['text'].strip()
            # 清理可能的 markdown 格式残留（如 ```json ... ``` 或 **bold** 等）
            translated = self._clean_translation(raw)
            return translated

    def _clean_translation(self, text):
        """清理翻译结果中的 markdown 残留格式"""
        # 去掉首尾可能的 markdown 代码块标记
        text = re.sub(r'^```(?:json|text)?\s*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        # 去掉残留的引号包裹（如 "> text" 或 "「text」"）
        text = re.sub(r'^[""「『](.+)[""」』]\s*$', r'\1', text, flags=re.DOTALL)
        # 去掉 **bold** / *italic* 等残留格式
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        return text.strip()

    def _translate_with_chat(self, endpoint, model_name, source_text):
        """使用 /v1/chat/completions API（适用于标准模型如 Qwen 等）"""
        url = endpoint.rstrip('/') + "/v1/chat/completions"

        src_lang = "Chinese" if is_chinese(source_text) else "English"
        tgt_lang = "English" if src_lang == "Chinese" else "Chinese"

        # 统一使用与 translategemma 一致的 prompt 格式，避免模型输出多选项
        user_message = (
            "Translate the following " + src_lang + " text into " + tgt_lang + ". "
            "Output ONLY the " + tgt_lang + " translation, no explanations, no alternatives, no options.\n\n"
            + source_text
        )

        data = {
            'messages': [
                {'role': 'user', 'content': user_message}
            ],
            'max_tokens': 4096,
            'temperature': 0.1,
            'stream': False
        }

        if model_name:
            data["model"] = model_name

        json_data = json.dumps(data).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        request = urllib.request.Request(url, data=json_data, headers=headers, method='POST')

        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            raw = result['choices'][0]['message']['content'].strip()
            translated = self._clean_translation(raw)
            return translated

    def translate_selection(self, doc_model):
        """翻译用户选中的文本，将译文插入原文下方"""
        text = doc_model.Text
        selection = doc_model.CurrentController.getSelection()
        text_range = selection.getByIndex(0)
        selected_text = text_range.getString().strip()

        if not selected_text:
            show_message(doc_model, "Translator", "No text selected. Please select text first.")
            return

        try:
            translated = self.translate_text(selected_text)

            # 在选中范围末尾创建光标，插入段落分隔和译文
            cursor = text.createTextCursorByRange(text_range.getEnd())
            text.insertControlCharacter(cursor, CTRL_PARAGRAPH_BREAK, False)
            text.insertString(cursor, translated, False)

        except Exception as e:
            log_to_file(f"translate_selection error: {traceback.format_exc()}")
            show_message(doc_model, "Translation Error", str(e))

    def translate_entire_document(self, doc_model):
        """翻译整个文档，逐段翻译并在原文下方插入译文"""
        text = doc_model.Text

        # 收集所有段落信息
        paragraphs = []
        para_cursor = text.createTextCursor()
        para_cursor.gotoStart(False)

        while True:
            # 记录当前段落起始位置
            para_start = text.createTextCursorByRange(para_cursor)

            try:
                # 选中当前段落内容
                para_cursor.gotoEndOfParagraph(True)
            except Exception:
                # 非文本区域（如表格/图片），尝试跳过
                try:
                    if not para_cursor.gotoNextParagraph(False):
                        break
                    continue
                except Exception:
                    break

            para_text = para_cursor.getString().strip()
            if para_text:
                # 保存段落结束位置
                para_end = text.createTextCursorByRange(para_cursor.getEnd())
                paragraphs.append({
                    'text': para_text,
                    'end_cursor': para_end,
                })

            # 移动到下一段
            try:
                if not para_cursor.gotoNextParagraph(False):
                    break
            except Exception:
                break

        if not paragraphs:
            show_message(doc_model, "Translator", "No translatable text found in the document.")
            return

        # 从后往前翻译插入，避免光标位置偏移
        errors = []
        for para_info in reversed(paragraphs):
            try:
                translated = self.translate_text(para_info['text'])
                insert_cursor = text.createTextCursorByRange(para_info['end_cursor'])
                text.insertControlCharacter(insert_cursor, CTRL_PARAGRAPH_BREAK, False)
                text.insertString(insert_cursor, translated, False)
            except Exception as e:
                errors.append(str(e))
                log_to_file(f"translate paragraph error: {traceback.format_exc()}")

        if errors:
            show_message(doc_model, "Translation Error",
                         f"Some paragraphs failed to translate:\n{errors[0]}")

    def trigger(self, args):
        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)
        doc_model = desktop.getCurrentComponent()

        if not hasattr(doc_model, "Text"):
            return

        try:
            if args == "TranslateSelection":
                self.translate_selection(doc_model)
            elif args == "TranslateDocument":
                self.translate_entire_document(doc_model)
            elif args == "settings":
                result = self.settings_box("Translator Settings")
                if "endpoint" in result and result["endpoint"].startswith("http"):
                    self.set_config("endpoint", result["endpoint"])
                if "model" in result:
                    self.set_config("model", result["model"])
        except Exception as e:
            log_to_file(f"trigger error: {traceback.format_exc()}")
            show_message(doc_model, "Error", str(e))

    def settings_box(self, title="", x=None, y=None):
        """设置对话框"""
        WIDTH = 600
        HORI_MARGIN = VERT_MARGIN = 8
        BUTTON_WIDTH = 100
        BUTTON_HEIGHT = 26
        HORI_SEP = 8
        VERT_SEP = 4
        LABEL_HEIGHT = BUTTON_HEIGHT + 5
        EDIT_HEIGHT = 24
        HEIGHT = VERT_MARGIN * 4 + LABEL_HEIGHT * 2 + VERT_SEP * 2 + EDIT_HEIGHT * 2 + BUTTON_HEIGHT
        import uno as _uno
        from com.sun.star.awt.PosSize import POS, SIZE, POSSIZE
        from com.sun.star.awt.PushButtonType import OK, CANCEL
        ctx = _uno.getComponentContext()

        def create(name):
            return ctx.getServiceManager().createInstanceWithContext(name, ctx)

        dialog = create("com.sun.star.awt.UnoControlDialog")
        dialog_model = create("com.sun.star.awt.UnoControlDialogModel")
        dialog.setModel(dialog_model)
        dialog.setVisible(False)
        dialog.setTitle(title)
        dialog.setPosSize(0, 0, WIDTH, HEIGHT, SIZE)

        def add(name, type, x_, y_, width_, height_, props):
            m = dialog_model.createInstance("com.sun.star.awt.UnoControl" + type + "Model")
            dialog_model.insertByName(name, m)
            control = dialog.getControl(name)
            control.setPosSize(x_, y_, width_, height_, POSSIZE)
            for key, value in props.items():
                setattr(m, key, value)

        label_width = WIDTH - BUTTON_WIDTH - HORI_SEP - HORI_MARGIN * 2

        add("label_endpoint", "FixedText", HORI_MARGIN, VERT_MARGIN, label_width, LABEL_HEIGHT,
            {"Label": "LM Studio API Endpoint:", "NoLabel": True})
        add("btn_ok", "Button", HORI_MARGIN + label_width + HORI_SEP, VERT_MARGIN,
            BUTTON_WIDTH, BUTTON_HEIGHT, {"PushButtonType": OK, "DefaultButton": True})
        add("edit_endpoint", "Edit", HORI_MARGIN, LABEL_HEIGHT,
            WIDTH - HORI_MARGIN * 2, EDIT_HEIGHT,
            {"Text": str(self.get_config("endpoint", "http://127.0.0.1:1234"))})

        add("label_model", "FixedText", HORI_MARGIN, LABEL_HEIGHT + VERT_MARGIN + VERT_SEP + EDIT_HEIGHT,
            label_width, LABEL_HEIGHT,
            {"Label": "Model Name (optional):", "NoLabel": True})
        add("edit_model", "Edit", HORI_MARGIN, LABEL_HEIGHT * 2 + VERT_MARGIN + VERT_SEP * 2 + EDIT_HEIGHT,
            WIDTH - HORI_MARGIN * 2, EDIT_HEIGHT,
            {"Text": str(self.get_config("model", ""))})

        frame = create("com.sun.star.frame.Desktop").getCurrentFrame()
        window = frame.getContainerWindow() if frame else None
        dialog.createPeer(create("com.sun.star.awt.Toolkit"), window)

        if window:
            ps = window.getPosSize()
            _x = ps.Width / 2 - WIDTH / 2
            _y = ps.Height / 2 - HEIGHT / 2
            dialog.setPosSize(_x, _y, 0, 0, POS)

        edit_endpoint = dialog.getControl("edit_endpoint")
        edit_endpoint.setFocus()

        if dialog.execute():
            result = {
                "endpoint": edit_endpoint.getModel().Text,
                "model": dialog.getControl("edit_model").getModel().Text
            }
        else:
            result = {}

        dialog.dispose()
        return result


# Starting from Python IDE
def main():
    try:
        ctx = XSCRIPTCONTEXT
    except NameError:
        ctx = officehelper.bootstrap()
        if ctx is None:
            print("ERROR: Could not bootstrap default Office.")
            sys.exit(1)
    job = MainJob(ctx)
    job.trigger("TranslateSelection")

# Starting from command line
if __name__ == "__main__":
    main()

# pythonloader loads a static g_ImplementationHelper variable
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    MainJob,
    "org.extension.translator.do",
    ("com.sun.star.task.Job",), )
# vim: set shiftwidth=4 softtabstop=4 expandtab:
