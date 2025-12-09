#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2021, Jim Miller'
__docformat__ = 'restructuredtext en'

import logging
logger = logging.getLogger(__name__)

import traceback, copy
import six
from six import text_type as unicode

from PyQt5.Qt import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                      QLineEdit, QFont, QGridLayout, QComboBox,
                      QCheckBox, QPushButton, QTabWidget, QScrollArea,
                      QButtonGroup, QRadioButton, QIntValidator, QLayout,
                      QSpacerItem)

from calibre.gui2 import dynamic, info_dialog
from calibre.utils.config import JSONConfig
from calibre.gui2.ui import get_gui

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubsplit.common_utils \
    import ( get_library_uuid, KeyboardConfigDialog, PrefsViewerDialog )

PREFS_NAMESPACE = 'EpubSplitPlugin'
PREFS_KEY_SETTINGS = 'settings'

PER_SECTION = 'per_section'
PER_N_SECTIONS = 'per_n_sections'
PER_N_SPLITS = 'per_n_splits'
NEW_BOOK_PER_LIST = [PER_SECTION, PER_N_SECTIONS, PER_N_SPLITS]
title_section = "新しい各本のタイトルは、上の目次で最初に含まれるセクションから取得されます（ここで編集可能）。"
NEW_BOOK_PER = {
    PER_SECTION:("セクションごとに新しい本",
                 "上で選択した<i>各</i>セクションに対して新しい本を作成します。" + "<br>" + title_section),
    PER_N_SECTIONS:("Nセクションごとに新しい本",
                    "上で選択した中からN個のセクションを含む新しい本を作成します。" + "<br>" + title_section),
    PER_N_SPLITS:("N冊の新しい本",
                  "上で選択したセクションを均等に分割してN冊の新しい本を作成します。" + "<br>" + title_section)
    }

# Set defaults used by all.  Library specific settings continue to
# take from here.
default_prefs = {}
default_prefs['editmetadata'] = False
default_prefs['show_checkedalways'] = False

default_prefs['copytoctitle'] = True
default_prefs['copytitle'] = True
default_prefs['copyauthors'] = True
default_prefs['copytags'] = True

default_prefs['copyrating'] = True
default_prefs['copydate'] = True
default_prefs['copyidentifiers'] = False
default_prefs['copypublisher'] = True
default_prefs['copypubdate'] = True

default_prefs['copylanguages'] = True
default_prefs['copyseries'] = True
default_prefs['copycommentstitle'] = True
default_prefs['copycommentscallink'] = False
default_prefs['copycommentsidurl'] = True
default_prefs['copycomments'] = True
default_prefs['copycover'] = True

default_prefs['custom_cols'] = {}

default_prefs['sourcecol'] = ''
default_prefs['sourcetemplate'] = "{title} by {authors}"

default_prefs['new_book_per'] = PER_SECTION
default_prefs['n_sections_num'] = '10'
default_prefs['orphans_num'] = '2'
default_prefs['n_splits_num'] = '3'

def set_library_config(library_config):
    get_gui().current_db.prefs.set_namespaced(PREFS_NAMESPACE,
                                              PREFS_KEY_SETTINGS,
                                              library_config)

def get_library_config():
    db = get_gui().current_db
    library_id = get_library_uuid(db)
    library_config = None
    # Check whether this is a configuration needing to be migrated
    # from json into database.  If so: get it, set it, wipe it from json.
    if library_id in old_prefs:
        #print("get prefs from old_prefs")
        library_config = old_prefs[library_id]
        set_library_config(library_config)
        del old_prefs[library_id]

    if library_config is None:
        #print("get prefs from db")
        library_config = db.prefs.get_namespaced(PREFS_NAMESPACE, PREFS_KEY_SETTINGS,
                                                 copy.deepcopy(default_prefs))
    return library_config

# This is where all preferences for this plugin *were* stored
# Remember that this name (i.e. plugins/epubsplit) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
old_prefs = JSONConfig('plugins/EpubSplit')

# fake out so I don't have to change the prefs calls anywhere.  The
# Java programmer in me is offended by op-overloading, but it's very
# tidy.
class PrefsFacade():
    def __init__(self,default_prefs):
        self.default_prefs = default_prefs
        self.libraryid = None
        self.current_prefs = None

    def _get_prefs(self):
        libraryid = get_library_uuid(get_gui().current_db)
        if self.current_prefs == None or self.libraryid != libraryid:
            #print("self.current_prefs == None(%s) or self.libraryid != libraryid(%s)"%(self.current_prefs == None,self.libraryid != libraryid))
            self.libraryid = libraryid
            self.current_prefs = get_library_config()
        return self.current_prefs

    def __getitem__(self,k):
        prefs = self._get_prefs()
        if k not in prefs:
            # some users have old JSON, but have never saved all the
            # options.
            if k in self.default_prefs:
                return self.default_prefs[k]
            else:
                return default_prefs[k]
        return prefs[k]

    def __setitem__(self,k,v):
        prefs = self._get_prefs()
        prefs[k]=v
        # self._save_prefs(prefs)

    def __delitem__(self,k):
        prefs = self._get_prefs()
        if k in prefs:
            del prefs[k]

    def save_to_db(self):
        set_library_config(self._get_prefs())

prefs = PrefsFacade(old_prefs)

class ConfigWidget(QWidget):

    def __init__(self, plugin_action):
        QWidget.__init__(self)
        self.plugin_action = plugin_action

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        tab_widget = QTabWidget(self)
        self.l.addWidget(tab_widget)

        self.basic_tab = BasicTab(self, plugin_action)
        tab_widget.addTab(self.basic_tab, '基本')

        self.columns_tab = CustomColumnsTab(self, plugin_action)
        tab_widget.addTab(self.columns_tab, 'カスタム列')

        self.newbookper_tab = NewBookPerTab(self, plugin_action)
        tab_widget.addTab(self.newbookper_tab, '分割設定')

    def save_settings(self):
        prefs['editmetadata'] = self.basic_tab.editmetadata.isChecked()
        prefs['show_checkedalways'] = self.basic_tab.show_checkedalways.isChecked()
        prefs['copytoctitle'] = self.basic_tab.copytoctitle.isChecked()
        prefs['copytitle'] = self.basic_tab.copytitle.isChecked()
        prefs['copyauthors'] = self.basic_tab.copyauthors.isChecked()
        prefs['copytags'] = self.basic_tab.copytags.isChecked()
        prefs['copylanguages'] = self.basic_tab.copylanguages.isChecked()
        prefs['copyseries'] = self.basic_tab.copyseries.isChecked()
        prefs['copycommentstitle'] = self.basic_tab.copycommentstitle.isChecked()
        prefs['copycommentscallink'] = self.basic_tab.copycommentscallink.isChecked()
        prefs['copycommentsidurl'] = self.basic_tab.copycommentsidurl.isChecked()
        prefs['copycomments'] = self.basic_tab.copycomments.isChecked()
        prefs['copycover'] = self.basic_tab.copycover.isChecked()
        prefs['copydate'] = self.basic_tab.copydate.isChecked()
        prefs['copyrating'] = self.basic_tab.copyrating.isChecked()
        prefs['copypubdate'] = self.basic_tab.copypubdate.isChecked()
        prefs['copyidentifiers'] = self.basic_tab.copyidentifiers.isChecked()
        prefs['copypublisher'] = self.basic_tab.copypublisher.isChecked()

        # Custom Columns tab
        colsmap = {}
        for (col,chkbx) in six.iteritems(self.columns_tab.custcol_checkboxes):
            if chkbx.isChecked():
                colsmap[col] = chkbx.isChecked()
            #print("colsmap[%s]:%s"%(col,colsmap[col]))
        prefs['custom_cols'] = colsmap

        prefs['sourcecol'] = unicode(self.columns_tab.sourcecol.itemData(self.columns_tab.sourcecol.currentIndex()))
        prefs['sourcetemplate'] = unicode(self.columns_tab.sourcetemplate.text())

        # NewBookPer tab
        prefs['new_book_per'] = NEW_BOOK_PER_LIST[self.newbookper_tab.radiogroup.checkedId()]
        # logger.debug(prefs['new_book_per'])
        prefs['n_sections_num'] = unicode(self.newbookper_tab.n_sections_num.text())
        prefs['orphans_num'] = unicode(self.newbookper_tab.orphans_num.text())
        prefs['n_splits_num'] = unicode(self.newbookper_tab.n_splits_num.text())


        prefs.save_to_db()

    def edit_shortcuts(self):
        self.save_settings()
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()

class BasicTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        QWidget.__init__(self)
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.editmetadata = QCheckBox('新しい本のメタデータを編集',self)
        self.editmetadata.setToolTip('各新しい本のエントリを作成した後、EPUBを作成する<i>前に</i>メタデータ編集ダイアログを表示します。<br>メタデータをダウンロードでき、EPUBに最新のメタデータが含まれるようにします。')
        self.editmetadata.setChecked(prefs['editmetadata'])
        self.l.addWidget(self.editmetadata)

        self.show_checkedalways = QCheckBox("'常に含める'チェックボックスを表示",self)
        self.show_checkedalways.setToolTip('有効にすると、各セクションにチェックボックスが表示されます。'+' '+
                                           'チェックされたセクションは<i>すべての</i>分割本に含まれます。<br>デフォルトのタイトルは最初の<i>選択された</i>セクションから取得され、セクションの順序はそのまま保持されます。')
        self.show_checkedalways.setChecked(prefs['show_checkedalways'])
        self.l.addWidget(self.show_checkedalways)
        self.l.addSpacing(5)

        label = QLabel('新しいEpubを作成する際、元の本からのメタデータコピーについて以下で選択してください。')
        label.setWordWrap(True)
        self.l.addWidget(label)

        self.copytoctitle = QCheckBox('最初に含まれる目次からタイトルを取得',self)
        self.copytoctitle.setToolTip('分割Epubに含まれる最初の目次エントリからタイトルをコピーします。\n下の「タイトルをコピー」より優先されます。')
        self.copytoctitle.setChecked(prefs['copytoctitle'])
        self.l.addWidget(self.copytoctitle)

        self.copytitle = QCheckBox('タイトルをコピー',self)
        self.copytitle.setToolTip('元のEpubから分割Epubへタイトルをコピーします。タイトルに "Split" が追加されます。')
        self.copytitle.setChecked(prefs['copytitle'])
        self.l.addWidget(self.copytitle)

        self.copyauthors = QCheckBox('著者をコピー',self)
        self.copyauthors.setToolTip('元のEpubから分割Epubへ著者をコピーします。')
        self.copyauthors.setChecked(prefs['copyauthors'])
        self.l.addWidget(self.copyauthors)

        self.copyseries = QCheckBox('シリーズをコピー',self)
        self.copyseries.setToolTip('元のEpubから分割Epubへシリーズをコピーします。')
        self.copyseries.setChecked(prefs['copyseries'])
        self.l.addWidget(self.copyseries)

        self.copycover = QCheckBox('表紙をコピー',self)
        self.copycover.setToolTip('元のEpubから分割Epubへ表紙をコピーします。')
        self.copycover.setChecked(prefs['copycover'])
        self.l.addWidget(self.copycover)

        self.copyrating = QCheckBox('評価をコピー',self)
        self.copyrating.setToolTip('元のEpubから分割Epubへ評価をコピーします。')
        self.copyrating.setChecked(prefs['copyrating'])
        self.l.addWidget(self.copyrating)

        self.copytags = QCheckBox('タグをコピー',self)
        self.copytags.setToolTip('元のEpubから分割Epubへタグをコピーします。')
        self.copytags.setChecked(prefs['copytags'])
        self.l.addWidget(self.copytags)

        self.copyidentifiers = QCheckBox('識別子(ID)をコピー',self)
        self.copyidentifiers.setToolTip('元のEpubから分割Epubへ識別子をコピーします。')
        self.copyidentifiers.setChecked(prefs['copyidentifiers'])
        self.l.addWidget(self.copyidentifiers)

        self.copydate = QCheckBox('日付をコピー',self)
        self.copydate.setToolTip('元のEpubから分割Epubへ日付をコピーします。')
        self.copydate.setChecked(prefs['copydate'])
        self.l.addWidget(self.copydate)

        self.copypubdate = QCheckBox('出版日をコピー',self)
        self.copypubdate.setToolTip('元のEpubから分割Epubへ出版日をコピーします。')
        self.copypubdate.setChecked(prefs['copypubdate'])
        self.l.addWidget(self.copypubdate)

        self.copypublisher = QCheckBox('出版社をコピー',self)
        self.copypublisher.setToolTip('元のEpubから分割Epubへ出版社をコピーします。')
        self.copypublisher.setChecked(prefs['copypublisher'])
        self.l.addWidget(self.copypublisher)

        self.copylanguages = QCheckBox('言語をコピー',self)
        self.copylanguages.setToolTip('元のEpubから分割Epubへ言語をコピーします。')
        self.copylanguages.setChecked(prefs['copylanguages'])
        self.l.addWidget(self.copylanguages)

        self.copycommentstitle = QCheckBox('元のタイトルをコメントにコピー',self)
        self.copycommentstitle.setToolTip('元のEpubのタイトルを分割Epubのコメントにコピーします。')
        self.copycommentstitle.setChecked(prefs['copycommentstitle'])
        self.l.addWidget(self.copycommentstitle)

        self.copycommentscallink = QCheckBox('Calibre内の元の本へのリンクをコメントに含める',self)
        self.copycommentscallink.setToolTip('元のEpubへのCalibreリンクを分割Epubのコメントに含めます。')
        self.copycommentscallink.setChecked(prefs['copycommentscallink'])
        self.l.addWidget(self.copycommentscallink)

        self.copycommentsidurl = QCheckBox('元のURL識別子へのリンクをコメントに含める',self)
        self.copycommentsidurl.setToolTip("元のEpubのURL識別子(存在する場合)へのリンクを分割Epubのコメントに含めます。")
        self.copycommentsidurl.setChecked(prefs['copycommentsidurl'])
        self.l.addWidget(self.copycommentsidurl)

        self.copycomments = QCheckBox('コメントをコピー',self)
        self.copycomments.setToolTip('元のEpubから分割Epubへコメントをコピーします。コメントに「分割元:」を追加します。')
        self.copycomments.setChecked(prefs['copycomments'])
        self.l.addWidget(self.copycomments)

        self.l.addSpacing(15)

        label = QLabel('これらのコントロールはプラグイン設定ではありませんが、キーボードショートカットの設定やすべてのEpubSplit確認ダイアログをリセットするための便利なボタンです。')
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)

        keyboard_shortcuts_button = QPushButton('キーボードショートカット...', self)
        keyboard_shortcuts_button.setToolTip('このプラグインに関連付けられたキーボードショートカットを編集します')
        keyboard_shortcuts_button.clicked.connect(parent_dialog.edit_shortcuts)
        self.l.addWidget(keyboard_shortcuts_button)

        reset_confirmation_button = QPushButton('無効化された確認ダイアログをリセット(&C)', self)
        reset_confirmation_button.setToolTip('EpubSplitプラグインのすべての「再表示しない」ダイアログをリセットします')
        reset_confirmation_button.clicked.connect(self.reset_dialogs)
        self.l.addWidget(reset_confirmation_button)

        view_prefs_button = QPushButton('ライブラリ設定を表示...', self)
        view_prefs_button.setToolTip('このプラグインのためにライブラリデータベースに保存されているデータを表示します')
        view_prefs_button.clicked.connect(self.view_prefs)
        self.l.addWidget(view_prefs_button)

    def view_prefs(self):
        d = PrefsViewerDialog(self.plugin_action.gui, PREFS_NAMESPACE)
        d.exec_()

    def reset_dialogs(self):
        for key in dynamic.keys():
            if key.startswith('epubsplit_') and key.endswith('_again') \
                                                  and dynamic[key] is False:
                dynamic[key] = True
        info_dialog(self, '完了',
                    '確認ダイアログはすべてリセットされました',
                    show=True,
                    show_copy_button=False)

class CustomColumnsTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action
        QWidget.__init__(self)

        custom_columns = self.plugin_action.gui.library_view.model().custom_columns

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel("ソース保存カラム:")
        label.setToolTip("設定すると、分割ファイルのソースを記録するために、以下のテンプレートで下の列が埋められます。")
        label.setWordWrap(True)
        self.l.addWidget(label)

        horz = QHBoxLayout()
        self.sourcecol = QComboBox(self)
        self.sourcecol.setToolTip("分割時にテンプレートで埋める列を選択します。")
        self.sourcecol.addItem('','none')
        ## sort by visible Column Name (vs #name)
        for key, column in sorted(custom_columns.items(), key=lambda x: x[1]['name']):
            if column['datatype'] in ('text','comments','series'):
                self.sourcecol.addItem(column['name'],key)
        self.sourcecol.setCurrentIndex(self.sourcecol.findData(prefs['sourcecol']))
        horz.addWidget(self.sourcecol)

        self.sourcetemplate = QLineEdit(self)
        self.sourcetemplate.setToolTip("元の本からのテンプレート。例: {title} by {authors}")
        # if 'sourcetemplate' in prefs:
        self.sourcetemplate.setText(prefs['sourcetemplate'])
        # else:
        #      self.sourcetemplate.setText("{title} by {authors}")
        horz.addWidget(self.sourcetemplate)

        self.l.addLayout(horz)
        self.l.addSpacing(5)

        label = QLabel("カスタム列が定義されている場合、以下にリストされます。これらの列を新しい分割された本にコピーするかどうかを選択してください。")
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)

        scrollable = QScrollArea()
        scrollcontent = QWidget()
        scrollable.setWidget(scrollcontent)
        scrollable.setWidgetResizable(True)
        self.l.addWidget(scrollable)

        self.sl = QVBoxLayout()
        scrollcontent.setLayout(self.sl)

        self.custcol_checkboxes = {}

        ## sort by visible Column Name (vs #name)
        for key, column in sorted(custom_columns.items(), key=lambda x: x[1]['name']):
            if column['datatype'] != 'composite':
                # print("\n============== %s ===========\n"%key)
                # for (k,v) in six.iteritems(column):
                #     print("column['%s'] => %s"%(k,v))
                checkbox = QCheckBox('%s(%s)'%(column['name'],key))
                checkbox.setToolTip("この %s 列を新しい分割された本にコピー..."%column['datatype'])
                checkbox.setChecked(key in prefs['custom_cols'] and prefs['custom_cols'][key])
                self.custcol_checkboxes[key] = checkbox
                self.sl.addWidget(checkbox)

        self.sl.insertStretch(-1)

class NewBookPerTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        QWidget.__init__(self)
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel('一度にアクティブにできる自動複数分割モードは1つだけです。以下で選択し、設定を行ってください。'
                       +'<p>'+'新しい各本のタイトルは、目次の最初に含まれるセクションから取得されます。'
                       +'<p>'+'目次エントリのないセクションは、前のセクションに含まれます。'
                       +'<p>'+'分割前に目次エントリを編集できます。')
        label.setWordWrap(True)
        self.l.addWidget(label)

        def indent_group(l):
            horz = QHBoxLayout()
            horz.addItem(QSpacerItem(20, 1))
            vertright = QVBoxLayout()
            horz.addLayout(vertright)
            for i in l:
                if isinstance(i,QLayout):
                    vertright.addLayout(i)
                else:
                    vertright.addWidget(i)
            self.l.addLayout(horz)

        def label_num_input(label,tooltip,minimum=0):
            horz = QHBoxLayout()
            label = QLabel(label)
            label.setToolTip(tooltip)
            edit = QLineEdit(self)
            edit.setToolTip(tooltip)
            label.setBuddy(edit)
            # allow only integers
            only_int = QIntValidator()
            only_int.setRange(minimum, 10000)
            edit.setValidator(only_int)
            edit.setMaximumWidth(100)
            horz.addWidget(label)
            horz.addWidget(edit)
            horz.insertStretch(-1)
            return (horz,edit)

        self.radiogroup = QButtonGroup()
        ## list incase I want to reorder.
        rb_idx = 0
        for n in NEW_BOOK_PER_LIST:
            rb = QRadioButton(NEW_BOOK_PER[n][0])
            rb.setToolTip(NEW_BOOK_PER[n][1])
            self.l.addWidget(rb)
            rb.setChecked(prefs['new_book_per'] == n)
            self.radiogroup.addButton(rb,rb_idx)
            rb_idx = rb_idx + 1
            indent_list = []
            if n == PER_SECTION:
                self.per_section = rb
                l1 = QLabel('選択した各セクションに対して新しい本を作成します。')
                l1.setWordWrap(True)
                indent_list = [l1]
            elif n == PER_N_SECTIONS:
                self.per_n_sections = rb
                l1 = QLabel('選択したN個のセクションごとに新しい本を作成します。')
                l1.setWordWrap(True)
                (n_sections_layout,
                 self.n_sections_num) = label_num_input('セクション数',
                                                       '新しい本あたりのセクション数',
                                                        minimum=2)
                l2 = QLabel('最後の本に含まれるセクション数が孤立制限よりも少ない場合、それらを前の本に含めます。その場合、最後の本はN個を超えるセクションを持ちます。')
                l2.setWordWrap(True)
                (orphans_layout,
                 self.orphans_num) = label_num_input('孤立制限',
                                                       '孤立セクションの制限')
                indent_list = [l1,
                               n_sections_layout,
                               orphans_layout,
                               l2]
                self.n_sections_num.setText(prefs['n_sections_num'])
                self.orphans_num.setText(prefs['orphans_num'])
            elif n == PER_N_SPLITS:
                self.per_n_splits = rb
                l1 = QLabel('選択したセクションをできるだけ均等に分割してN冊の新しい本を作成します。'
                            +'<p>'+'「均等」とは、ファイルやバイトサイズ、単語数ではなく、目次にエントリがあるセクションの数を意味することに注意してください。')
                l1.setWordWrap(True)
                (n_splits_layout,
                 self.n_splits_num) = label_num_input('本の数',
                                                       '選択したすべてのセクションをこの数の新しい本に分割し、セクションを均等に分けます。',
                                                      minimum=2)
                indent_list = [l1,n_splits_layout]
                self.n_splits_num.setText(prefs['n_splits_num'])
            indent_group(indent_list)
            self.l.addSpacing(5)
        self.l.insertStretch(-1)
