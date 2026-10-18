QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: #e6e6e6; }
QMainWindow, QWidget { background: #1e1f22; }
QListWidget#nav { background: #17181a; border: 0; min-width: 170px; outline: 0; }
QListWidget#nav::item { padding: 10px 14px; border-left: 3px solid transparent; }
QListWidget#nav::item:selected { background: #26282c; border-left: 3px solid #d7263d; }
QTableView, QTableWidget, QPlainTextEdit, QLineEdit, QTextEdit, QSpinBox, QComboBox
 { background: #25272b; border: 1px solid #33363b; gridline-color: #2f3237; selection-background-color: #5a1f29; }
QHeaderView::section { background: #2b2d31; padding: 4px; border: 0; border-right: 1px solid #33363b; }
QPushButton { background: #2f3237; border: 1px solid #3d4046; padding: 6px 12px; border-radius: 3px; }
QPushButton:hover { border-color: #d7263d; }
QPushButton#primary { background: #d7263d; border-color: #d7263d; color: white; }
QTabWidget::pane { border: 1px solid #33363b; }
QTabBar::tab { background: #25272b; padding: 6px 14px; }
QTabBar::tab:selected { background: #2f3237; border-bottom: 2px solid #d7263d; }
QProgressBar { background: #25272b; border: 1px solid #33363b; text-align: center; }
QProgressBar::chunk { background: #d7263d; }
QStatusBar { background: #17181a; }
QLabel#h1 { font-size: 20px; font-weight: 600; }
QLabel#warn { color: #ffb347; }
QLabel#muted { color: #8b8f96; }
"""
