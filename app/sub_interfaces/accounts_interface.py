
from typing import Union
from qfluentwidgets import SettingCard, SettingCardGroup, ListWidget, FluentIconBase, CardWidget, FluentStyleSheet
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QListWidgetItem, QVBoxLayout, QMessageBox, QInputDialog, QLineEdit, QLabel
from PySide6.QtWidgets import QGridLayout, QFrame
from qfluentwidgets import FluentIcon as FIF
from app.common.icon import UiIcon
from module.config import cfg
from app.tools.account_manager import accounts, reload_all_account_from_files, dump_current_account, delete_account, \
    save_account_name, import_account, save_acc_and_pwd, clear_reg
from app.tools import account_manager
from app.tools import config_profile
from app.tools.config_profile import (ensure_account_configs, is_customized,
                                      remove_account_config)
from module.logger import log
from module.localization import tr


class AccountsCard(QFrame):

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(parent=parent)
        FluentStyleSheet.SETTING_CARD.apply(self)
        self.setFixedHeight(500)
        #
        self.widget = ListWidget()
        self.wLayout = QGridLayout()
        self.wLayout.addWidget(self.widget)
        # self.widget.setStyleSheet("QListWidget{border: 1px solid #d9d9d9;} QListWidget::item{height: 30px;} QListWidget::item:selected{background-color: #f0f0f0;} QListWidget::item:hover{background-color: #f0f0f0;}")
        #
        self.buttons = QVBoxLayout()
        self.buttons.setContentsMargins(10, 3, 10, 3)
        self.tipsText = QLabel(tr("重要：请完全进入游戏（看到角色）后再进行导出，否则会读取前一个账号的UID，导致文件和账号不对应"))
        self.tipsText.setWordWrap(True)
        self.tipsText.setStyleSheet('color: #f94e9b')
        self.tipsText2 = QLabel(tr("该功能不支持云·星穹铁道"))
        self.tipsText2.setWordWrap(True)
        self.tipsText2.setStyleSheet('color: #f94e9b')
        self.buttons.addWidget(self.tipsText)
        self.buttons.addWidget(self.tipsText2)
        self.tipsText.setFixedHeight(50)
        self.tipsText2.setFixedHeight(50)
        self.addAccountButton = QPushButton(tr("导出当前游戏账户"), self)
        self.importAccountButton = QPushButton(tr("导入选中的账户"), self)
        self.deleteAccountButton = QPushButton(tr("删除账户"), self)
        self.renameAccountButton = QPushButton(tr("账户更名"), self)
        self.autologinAccountButton = QPushButton(tr("自动登录"), self)
        self.refreshAccountButton = QPushButton(tr("刷新"), self)
        self.clearRegButton = QPushButton(tr("清除注册表"), self)
        self.followConfigButton = QPushButton(self)
        self.followConfigButton.setCheckable(True)
        self.followConfigButton.setToolTip(tr("开启后每个账号使用自己的配置；关闭时所有账号共用同一份配置"))
        self.copyConfigButton = QPushButton(tr("复制配置"), self)
        self.copyConfigButton.setToolTip(tr("把选中账号的配置替换为其他账号或官方默认配置"))
        self.multiRunButton = QPushButton(self)
        self.multiRunButton.setCheckable(True)
        self.multiRunButton.setToolTip(
            tr("开启后，在主界面点击“开始运行”将依次运行所有已导出的账号（每个账号跑完自动切换下一个）"))
        self.buttons.addWidget(self.addAccountButton)
        self.buttons.addWidget(self.importAccountButton)
        self.buttons.addWidget(self.deleteAccountButton)
        self.buttons.addWidget(self.renameAccountButton)
        self.buttons.addWidget(self.autologinAccountButton)
        self.buttons.addWidget(self.refreshAccountButton)
        self.buttons.addWidget(self.clearRegButton)
        self.buttons.addWidget(self.followConfigButton)
        self.buttons.addWidget(self.copyConfigButton)
        self.buttons.addWidget(self.multiRunButton)
        _self = self

        def updateFollowConfigButton():
            enabled = config_profile.is_enabled()
            # 阻止程序化改状态触发 toggled 回调，避免打开页面时误改配置
            _self.followConfigButton.blockSignals(True)
            _self.followConfigButton.setChecked(enabled)
            _self.followConfigButton.blockSignals(False)
            _self.followConfigButton.setText(
                tr("配置跟随账号：开") if enabled else tr("配置跟随账号：关"))

        def updateMultiRunButton():
            enabled = bool(cfg.get_value('multi_account_run_enable', False))
            # 阻止程序化改状态触发 toggled 回调，避免打开页面时误改配置
            _self.multiRunButton.blockSignals(True)
            _self.multiRunButton.setChecked(enabled)
            _self.multiRunButton.blockSignals(False)
            _self.multiRunButton.setText(
                tr("多账号连跑：开") if enabled else tr("多账号连跑：关"))

        def load_accounts():
            _self.widget.clear()
            for account in accounts:
                texts = [account.account_name]
                if config_profile.is_enabled():
                    if config_profile.get_loaded_account() == account.account_id:
                        texts.append(tr("[当前]"))
                    # 只标出「已经被改过」的账号；刚建立、还没动过的账号不标记
                    if is_customized(account.account_id):
                        texts.append(tr("[已自定义]"))
                item = QListWidgetItem(" ".join(texts))
                item.setData(Qt.ItemDataRole.UserRole, account.account_id)
                _self.widget.addItem(item)
            _self.widget.clearSelection()
        updateFollowConfigButton()
        updateMultiRunButton()
        try:
            load_accounts()
        except Exception as e:
            log.error(f"load_accounts: {e}")

        def refreshAccountButtonAction(self):
            reload_all_account_from_files()
            load_accounts()
            QMessageBox.information(None, tr("刷新"), tr("账户列表刷新成功"))

        def addAccountButtonAction(self):
            dump_current_account()
            load_accounts()
            QMessageBox.information(None, tr("导出"), tr("账户导出成功"))

        def deleteAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("删除账户"), tr("请选择要删除的账户"))
                return
            if QMessageBox.question(None, tr("删除账户"), tr("确定要删除选中的账户吗？"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                delete_account(account_id)
                # 账号被删除时，顺手清掉它自己的那份配置，避免留下无主文件
                remove_account_config(account_id)
            load_accounts()

        def renameAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("账户更名"), tr("请选择要更名的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("账户更名"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                account_name, ok = QInputDialog.getText(None, tr("账户更名"), tr("请输入新的账户名"))
                if ok:
                    account_name = account_name.strip()
                    if len(account_name) == 0:
                        QMessageBox.warning(None, tr("账户更名"), tr("账户名不能为空"))
                        return
                    save_account_name(account_id, account_name)
                    load_accounts()

        def autologinAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("自动登录"), tr("请选择要使用的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("自动登录"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)

                disclaimer_result = QMessageBox.question(
                    None,
                    tr("自动登录"),
                    tr("当登录过期时尝试自动重新填写账号密码\n *此功能存在一定风险，请谨慎使用*"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if disclaimer_result != QMessageBox.StandardButton.Yes:
                    return

                account_name, ok = QInputDialog.getText(None, tr("自动登录"), tr("请输入用户名"))
                if not ok:
                    return
                if not account_name.strip():
                    QMessageBox.warning(None, tr("自动登录"), tr("用户名不能为空"))
                    return

                account_pass, ok2 = QInputDialog.getText(None, tr("自动登录"), tr("请输入密码"), QLineEdit.EchoMode.Password)
                if not ok2:
                    return
                if not account_pass.strip():
                    QMessageBox.warning(None, tr("自动登录"), tr("密码不能为空"))
                    return

                save_acc_and_pwd(account_id, account_name, account_pass)

        def importAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("导入"), tr("请选择要使用的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("导入"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                import_account(account_id)
                QMessageBox.information(None, tr("导入"), tr("账户导入成功"))

        def clearRegButtonAction(self):
            if QMessageBox.question(None, tr("清除注册表"), tr("确定要清除注册表中的账户信息吗？"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return
            clear_reg()
            QMessageBox.information(None, tr("清除注册表"), tr("注册表中的账户信息已清除"))

        self.addAccountButton.clicked.connect(addAccountButtonAction)
        self.importAccountButton.clicked.connect(importAccountButtonAction)
        self.refreshAccountButton.clicked.connect(refreshAccountButtonAction)
        self.renameAccountButton.clicked.connect(renameAccountButtonAction)
        self.autologinAccountButton.clicked.connect(autologinAccountButtonAction)
        self.deleteAccountButton.clicked.connect(deleteAccountButtonAction)
        self.clearRegButton.clicked.connect(clearRegButtonAction)

        def followConfigButtonAction(checked):
            created = 0
            if checked:
                # 先按当前配置「收养」正在使用的账号，再给其余账号各建一份默认配置，
                # 这样一打开开关，列表里每个账号就都已经有自己的配置了。
                config_profile.set_enabled(True)
                created = ensure_account_configs(
                    [a.account_id for a in accounts])
            else:
                config_profile.set_enabled(False)
            updateFollowConfigButton()
            load_accounts()
            if checked:
                QMessageBox.information(
                    None, tr("配置跟随账号"),
                    tr("已开启：每个账号使用自己的配置。\n"
                       "当前正在使用的配置已保存为当前账号的配置，"
                       f"另有 {created} 个账号已按官方默认配置建立各自的配置。"))
            else:
                QMessageBox.information(
                    None, tr("配置跟随账号"),
                    tr("已关闭：所有账号共用同一份配置（已保存的账号配置不会被删除）。"))

        def copyConfigButtonAction():
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("复制配置"), tr("请选择要复制配置到的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("复制配置"), tr("只能选择一个账户"))
                return
            dst_id = items[0].data(Qt.ItemDataRole.UserRole)

            sources = []
            for account in accounts:
                if account.account_id != dst_id:
                    sources.append((f"{account.account_name}（{account.account_id}）", account.account_id))
            labels = [tr("官方默认配置")] + [s[0] for s in sources]
            text, ok = QInputDialog.getItem(
                None, tr("复制配置"), tr("选择要复制过来的配置来源（将覆盖目标账号现有配置）"), labels, 0, False)
            if not ok:
                return
            try:
                index = labels.index(text)
            except ValueError:
                return
            src_id = None if index == 0 else sources[index - 1][1]
            if config_profile.copy_account_config(src_id, dst_id):
                load_accounts()
                QMessageBox.information(None, tr("复制配置"), tr("配置已复制"))
            else:
                QMessageBox.warning(None, tr("复制配置"), tr("复制失败，请查看日志"))

        def multiRunButtonAction(checked):
            if checked:
                # 没有任何已导出账号时禁止开启，避免用户开了开关却一直没反应
                account_manager.reload_all_account_from_files()
                if not account_manager.accounts:
                    cfg.set_value('multi_account_run_enable', False)
                    updateMultiRunButton()
                    QMessageBox.warning(
                        None, tr("多账号连跑"),
                        tr("还没有任何已导出的账号。\n请先对每个账号执行“导出当前游戏账户”后再开启。"))
                    return
            cfg.set_value('multi_account_run_enable', bool(checked))
            updateMultiRunButton()
            if checked:
                QMessageBox.information(
                    None, tr("多账号连跑"),
                    tr("已开启：在主界面点击“开始运行”时，将依次运行所有已导出的账号，"
                       "每个账号跑完自动切换下一个，结束后发送汇总通知。\n"
                       "定时任务不受影响，仍按原配置运行当前账号。"))
            else:
                QMessageBox.information(
                    None, tr("多账号连跑"),
                    tr("已关闭：“开始运行”仅运行当前账号。"))

        self.followConfigButton.toggled.connect(followConfigButtonAction)
        self.copyConfigButton.clicked.connect(copyConfigButtonAction)
        self.multiRunButton.toggled.connect(multiRunButtonAction)
        #
        self.mLayout = QGridLayout()
        self.mLayout.addLayout(self.wLayout, 0, 0, 1, 1)
        self.mLayout.addLayout(self.buttons, 0, 1, 1, 1)
        self.mLayout.setColumnStretch(0, 1)  # 第一列的拉伸因子为1，即均分空间
        self.mLayout.setColumnStretch(1, 1)  # 第二列的拉伸因子为1，即均分空间
        #
        self.setLayout(self.mLayout)


def accounts_interface(tr, scrollWidget) -> SettingCardGroup:
    accountsInterface = SettingCardGroup(tr("账户设置"), scrollWidget)
    accountsInterface.addSettingCard(AccountsCard(
        UiIcon.PERSON, title=tr(""),
    ))
    return accountsInterface
