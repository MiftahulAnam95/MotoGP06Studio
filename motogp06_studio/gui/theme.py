QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: #e8eaf0; }
QMainWindow, QWidget { background: #17191e; }
QWidget#centralWidget { background: #17191e; }
QListWidget#nav {
    background: #111318; border: 0; min-width: 205px; max-width: 205px;
    outline: 0; padding: 12px 8px;
}
QListWidget#nav::item { padding: 12px 13px; margin: 2px 0; border-radius: 6px; border-left: 3px solid transparent; }
QListWidget#nav::item:hover { background: #22252c; }
QListWidget#nav::item:selected { background: #2a2026; border-left: 3px solid #f04b5d; color: #ffffff; }
QTableView, QTableWidget, QPlainTextEdit, QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #20232a; border: 1px solid #343943; border-radius: 5px;
    gridline-color: #343943; selection-background-color: #6a2934;
}
QTableWidget { alternate-background-color: #23262d; }
QTableView { alternate-background-color: #23262d; }
QHeaderView::section { background: #292d35; padding: 7px; border: 0; border-right: 1px solid #343943; }
QPushButton {
    background: #292d35; border: 1px solid #414652; padding: 8px 13px;
    border-radius: 5px; min-height: 18px;
}
QPushButton:hover { background: #343943; border-color: #f04b5d; }
QPushButton:pressed { background: #20232a; }
QPushButton#primary { background: #d9364c; border-color: #d9364c; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #ed465c; }
QTabWidget::pane { border: 1px solid #343943; border-radius: 4px; }
QTabBar::tab { background: #20232a; padding: 8px 15px; }
QTabBar::tab:selected { background: #292d35; border-bottom: 2px solid #f04b5d; }
QProgressBar { background: #20232a; border: 1px solid #343943; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #d9364c; border-radius: 4px; }
QStatusBar { background: #111318; }
QLabel#h1 { font-size: 22px; font-weight: 650; padding: 4px 0; }
QLabel#warn { color: #ffd180; background: #322b20; border-left: 3px solid #d99a34; padding: 9px 12px; border-radius: 4px; }
QLabel#muted { color: #adb3be; }
QLabel#card { color: #eff1f5; background: #22262d; border: 1px solid #343943; padding: 14px; border-radius: 7px; }
"""
