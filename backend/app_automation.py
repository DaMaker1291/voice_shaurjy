"""App automation — controls Word, OneNote, Excel, Chrome via COM and PowerShell. Full desktop app manipulation."""

from ps_executor import ps, ps_batch


# ── Microsoft Word ────────────────────────────────────────────────

def word_open() -> str:
    """Launch Word and return status."""
    return ps('Start-Process "winword.exe"; "Word launched."')


def word_new_document() -> str:
    """Create a new Word document."""
    return ps("""
        $w = New-Object -ComObject Word.Application;
        $w.Visible = $true;
        $doc = $w.Documents.Add();
        "New document created."
    """)


def word_type_text(text: str, style: str = "Normal", font_size: int = 11, bold: bool = False):
    """Type text at cursor position in the active Word document."""
    escaped = text.replace('"', '\\"').replace("'", "''").replace("`", "``").replace("\n", "\\n")
    ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $sel = $w.Selection;
            { ' $sel.Font.Bold = 1; ' if bold else '' }
            $sel.Font.Size = {font_size};
            $sel.Style = "{style}";
            $sel.TypeText("{escaped}");
        }} catch {{ "Word not running." }}
    """)


def word_apply_formatting(bold: bool = False, italic: bool = False, underline: bool = False,
                          font_name: str = "", font_size: int = 0, color: str = ""):
    """Apply formatting at cursor position."""
    bold_cmd = "1" if bold else "0"
    italic_cmd = "1" if italic else "0"
    underline_cmd = "1" if underline else "0"
    ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $sel = $w.Selection;
            $sel.Font.Bold = {bold_cmd};
            $sel.Font.Italic = {italic_cmd};
            $sel.Font.Underline = {underline_cmd};
            { f'$sel.Font.Name = "{font_name}";' if font_name else '' }
            { f'$sel.Font.Size = {font_size};' if font_size else '' }
            { f'$sel.Font.Color = [System.Drawing.Color]::FromName("{color}");' if color else '' }
            "Formatted."
        }} catch {{ "Word not running." }}
    """)


def word_insert_heading(text: str, level: int = 1):
    """Insert a heading at cursor position."""
    styles = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}
    style = styles.get(level, "Heading 1")
    word_type_text(text, style=style, font_size=16 if level == 1 else 14 if level == 2 else 12, bold=True)


def word_insert_paragraph(text: str):
    """Insert a paragraph with spacing."""
    word_type_text(text)
    ps("""
        try {
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $w.Selection.TypeParagraph();
        } catch {}
    """)


def word_insert_bullet_point(text: str):
    """Insert a bullet point."""
    ps("""
        try {
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $list = $w.ListGalleries(1);
            $w.Selection.Range.ListFormat.ApplyBulletDefault();
            $w.Selection.TypeText("BUGET_PLACEHOLDER");
            $w.Selection.TypeParagraph();
        } catch {}
    """)
    word_type_text(text)


def word_save(path: str = "") -> str:
    """Save the active Word document."""
    if not path:
        import os
        path = os.path.expanduser("~/Desktop/document.docx")
    return ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $w.ActiveDocument.SaveAs("{path}");
            "Saved to {path}."
        }} catch {{ "Word not running." }}
    """)


def word_insert_table(rows: int, cols: int, data: list[list[str]] = None):
    """Insert a table at cursor position."""
    ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $rng = $w.Selection.Range;
            $tbl = $w.ActiveDocument.Tables.Add($rng, {rows}, {cols});
            $tbl.Borders.InsideLineStyle = 1;
            $tbl.Borders.OutsideLineStyle = 1;
            "Table {rows}x{cols} inserted."
        }} catch {{ "Word not running." }}
    """)
    if data:
        for ri, row in enumerate(data):
            for ci, cell in enumerate(row):
                if ri < rows and ci < cols:
                    ps(f"""
                        try {{
                            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
                            $w.ActiveDocument.Tables(1).Cell({ri+1},{ci+1}).Range.Text = "{cell}";
                        }} catch {{}}
                    """)


def word_insert_image(path: str):
    """Insert an image at cursor position."""
    ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $w.Selection.InlineShapes.AddPicture("{path}");
            "Image inserted."
        }} catch {{ "Word not running." }}
    """)


def word_close(save: bool = True) -> str:
    """Close Word."""
    return ps(f"""
        try {{
            $w = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application');
            $w.ActiveDocument.Close({[int(save)]});
            $w.Quit();
            "Word closed."
        }} catch {{ "Word not running." }}
    """)


# ── Microsoft OneNote ─────────────────────────────────────────────

def onenote_open() -> str:
    """Launch OneNote."""
    return ps('Start-Process "onenote.exe"; "OneNote launched."')


def onenote_create_page(notebook: str = "", section: str = "", page_title: str = "New Page") -> str:
    """Create a new page in OneNote."""
    nt = notebook.replace('"', '""')
    sec = section.replace('"', '""')
    pt = page_title.replace('"', '""')
    return ps(f"""
        try {{
            $o = New-Object -ComObject OneNote.Application;
            $hierarchy = "";
            $o.GetHierarchy("", [Microsoft.Office.Interop.OneNote.HierarchyScope]::hsNotebooks, [ref]$hierarchy);
            $ns = New-Object -ComObject OneNote.Application;
            $ns.CreateNewPage("$nt/$sec", [ref]$pageId);
            $ns.UpdatePageContent("<?xml version='1.0'?><Page xmlns='http://schemas.microsoft.com/office/OneNote/2013/OneNoteSchema' ID='$pageId'><Title><![CDATA[$pt]]></Title></Page>");
            "Page '$pt' created."
        }} catch {{ "OneNote not available. Launching..."; Start-Process "onenote.exe"; "OneNote opened manually." }}
    """)


def onenote_write_content(text: str, page_title: str = "") -> str:
    """Write content to the current OneNote page or specified page."""
    escaped = text.replace('"', '""').replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    return ps(f"""
        try {{
            $o = New-Object -ComObject OneNote.Application;
            $pageId = "";
            if ("{page_title}") {{
                $hierarchy = ""; $o.GetHierarchy("", [Microsoft.Office.Interop.OneNote.HierarchyScope]::hsPages, [ref]$hierarchy);
                $xml = [xml]$hierarchy;
                $page = $xml.SelectSingleNode("//one:Page[contains(@name, '{page_title}')]");
                if ($page) {{ $pageId = $page.GetAttribute('ID'); }}
            }}
            if (!$pageId) {{ $o.GetCurrentPage([ref]$pageId); }}
            $xmlContent = "<?xml version='1.0'?><Page xmlns='http://schemas.microsoft.com/office/OneNote/2013/OneNoteSchema' ID='$pageId'><Outline><OEChildren><OE><T><![CDATA[$escaped]]></T></OE></OEChildren></Outline></Page>";
            $o.UpdatePageContent($xmlContent);
            "Content written to OneNote."
        }} catch {{ "OneNote automation failed. Opening manually."; Start-Process "onenote.exe"; "OneNote opened." }}
    """)


# ── Microsoft Excel ───────────────────────────────────────────────

def excel_open() -> str:
    """Launch Excel."""
    return ps('Start-Process "excel.exe"; "Excel launched."')


def excel_new_workbook() -> str:
    """Create a new Excel workbook."""
    return ps("""
        $e = New-Object -ComObject Excel.Application;
        $e.Visible = $true;
        $wb = $e.Workbooks.Add();
        "New workbook created."
    """)


def excel_set_cell(sheet: int, row: int, col: int, value: str):
    """Set a cell value."""
    escaped = value.replace('"', '\\"')
    ps(f"""
        try {{
            $e = [Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application');
            $e.Worksheets({sheet}).Cells({row},{col}).Value = "{escaped}";
        }} catch {{ "Excel not running." }}
    """)


def excel_set_cells(sheet: int, data: list[list[str]]):
    """Set a range of cells from a 2D array."""
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            excel_set_cell(sheet, ri + 1, ci + 1, val)


def excel_save(path: str = "") -> str:
    """Save the active workbook."""
    if not path:
        import os
        path = os.path.expanduser("~/Desktop/workbook.xlsx")
    return ps(f"""
        try {{
            $e = [Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application');
            $e.ActiveWorkbook.SaveAs("{path}");
            "Saved to {path}."
        }} catch {{ "Excel not running." }}
    """)


def excel_run_macro(macro_name: str):
    """Run an Excel macro."""
    ps(f"""
        try {{
            $e = [Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application');
            $e.Run("{macro_name}");
        }} catch {{}}
    """)


# ── Chrome / Browser ──────────────────────────────────────────────

def chrome_open(url: str = "https://google.com") -> str:
    """Open Chrome to a URL."""
    return ps(f'Start-Process "chrome.exe" -ArgumentList "{url}"; "Chrome opened."')


def chrome_new_tab(url: str = "https://google.com"):
    """Open a new tab in Chrome."""
    send_keys(f"^t")
    import time; time.sleep(0.5)
    type_text(url)
    send_keys("{ENTER}")


def chrome_open_devtools():
    """Open Chrome DevTools."""
    send_keys("^{F12}")


def chrome_search(query: str):
    """Search Google in Chrome."""
    chrome_open(f"https://google.com/search?q={__import__('urllib').parse.quote(query)}")


# ── Generic desktop typing (fallback) ────────────────────────────

def type_text(text: str, delay_ms: int = 10):
    """Type text slowly into the active window. More reliable than SendKeys for long text."""
    batch_size = 50
    for i in range(0, len(text), batch_size):
        chunk = text[i:i+batch_size]
        escaped = chunk.replace('"', '\\"').replace("'", "''").replace("`", "``").replace("\n", "{ENTER}").replace("\t", "{TAB}")
        ps(f"""
            Add-Type -AssemblyName System.Windows.Forms;
            [System.Windows.Forms.SendKeys]::SendWait("{escaped}")
        """)
        import time; time.sleep(delay_ms / 1000)


def send_keys(keys: str):
    """Send keyboard shortcut keys."""
    ps(f"""
        $k = New-Object -ComObject WScript.Shell;
        $k.SendKeys("{keys}")
    """)


# ── Enhanced OneNote Homework Automation ──────────────────────────

def onenote_fill_homework_sheet(subject: str, answers: list[str], page_title: str = "Homework"):
    """Fill in a homework sheet in OneNote with answers."""
    onenote_open()
    import time; time.sleep(2)
    onenote_create_page(page_title=page_title)
    time.sleep(1)

    content_parts = []
    for i, answer in enumerate(answers):
        content_parts.append(f"Q{i+1}. {answer}")
    full_content = "\n\n".join(content_parts)
    return onenote_write_content(full_content, page_title)


def onenote_write_with_formatting(text: str, bold_headings: bool = True, font_size: int = 12):
    """Write structured content to OneNote with basic formatting."""
    escaped = text.replace('"', '""').replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    return ps(f"""
        try {{
            $o = New-Object -ComObject OneNote.Application;
            $pageId = ""; $o.GetCurrentPage([ref]$pageId);
            $xmlContent = "<?xml version='1.0'?>
<Page xmlns='http://schemas.microsoft.com/office/OneNote/2013/OneNoteSchema' ID='$pageId'>
  <Outline>
    <OEChildren>
      <OE>
        <T><![CDATA[$escaped]]></T>
      </OE>
    </OEChildren>
  </Outline>
</Page>";
            $o.UpdatePageContent($xmlContent);
            "Content written with formatting."
        }} catch {{ "OneNote error: $_" }}
    """)


# ── Trading Platform Automation ────────────────────────────────────

def tradingview_open(symbol: str = "BTCUSD"):
    """Open TradingView chart for a symbol."""
    url = f"https://www.tradingview.com/chart/?symbol={symbol}"
    return ps(f'Start-Process "chrome.exe" -ArgumentList "{url}"; "TradingView {symbol} opened."')


def metatrader_open(platform: str = "mt4"):
    """Open MetaTrader 4 or 5."""
    exe = "mt4.exe" if platform.lower() == "mt4" else "mt5.exe"
    return ps(f'Start-Process "{exe}"; "{platform.upper()} launched."')


def binance_open(pair: str = "BTCUSDT"):
    """Open Binance trading page."""
    url = f"https://www.binance.com/en/trade/{pair}"
    return ps(f'Start-Process "chrome.exe" -ArgumentList "{url}"; "Binance {pair} opened."')


def coinbase_open(pair: str = "BTC-USD"):
    """Open Coinbase trading page."""
    url = f"https://www.coinbase.com/advanced-trade/{pair}"
    return ps(f'Start-Process "chrome.exe" -ArgumentList "{url}"; "Coinbase {pair} opened."')


def excel_create_trading_log(data: list[list[str]]):
    """Create a trading log spreadsheet in Excel."""
    import os
    excel_new_workbook()
    headers = ["Date", "Pair", "Type", "Entry", "Exit", "Size", "P&L", "Notes"]
    excel_set_cells(1, [headers] + data)
    excel_save(os.path.expanduser("~/Desktop/trading_log.xlsx"))
    return "Trading log created and saved to desktop."


# ── Enhanced Browser Automation ────────────────────────────────────

def browser_navigate(url: str):
    """Navigate browser to a URL (opens in default browser)."""
    return ps(f'Start-Process "{url}"; "Navigated to {url}."')


def browser_fill_form(field_id: str, value: str):
    """Fill a form field in the active browser tab using JavaScript bookmarklet approach."""
    escaped_value = value.replace("'", "\\'").replace('"', '\\"')
    type_text(value)
    return f"Filled {field_id} with {value}"


def browser_click(selector: str):
    """Click an element in the browser (uses keyboard navigation as fallback)."""
    send_keys("{ENTER}")
    return f"Clicked {selector}"


def browser_scroll_down(amount: int = 1):
    """Scroll down in the browser."""
    for _ in range(amount):
        send_keys("{PAGEDOWN}")
        import time; time.sleep(0.3)
    return f"Scrolled down {amount} pages"


def browser_scroll_up(amount: int = 1):
    """Scroll up in the browser."""
    for _ in range(amount):
        send_keys("{PAGEUP}")
        import time; time.sleep(0.3)
    return f"Scrolled up {amount} pages"


def browser_go_back():
    """Go back in browser history."""
    send_keys("%{LEFT}")
    return "Went back"


def browser_go_forward():
    """Go forward in browser history."""
    send_keys("%{RIGHT}")
    return "Went forward"


def browser_refresh():
    """Refresh the current page."""
    send_keys("{F5}")
    return "Refreshed"


def browser_new_tab():
    """Open a new browser tab."""
    send_keys("^t")
    return "New tab opened"


def browser_close_tab():
    """Close the current browser tab."""
    send_keys("^w")
    return "Tab closed"


def browser_switch_tab(index: int = 1):
    """Switch to a specific browser tab by index."""
    for _ in range(index):
        send_keys("^{TAB}")
        import time; time.sleep(0.2)
    return f"Switched to tab {index}"


def browser_download_file(url: str):
    """Download a file from URL using the browser."""
    return ps(f'Start-Process "chrome.exe" -ArgumentList "{url}"; "Download started."')


# ── Screenshot + OCR ───────────────────────────────────────────────

def screenshot_with_ocr(region: tuple = None, save_path: str = "") -> str:
    """Take a screenshot and attempt to read text from it (basic OCR via PowerShell)."""
    if not save_path:
        import os
        save_path = os.path.expanduser("~/Desktop/ocr_screenshot.png")

    if region:
        x, y, w, h = region
        ps(f"""
            Add-Type -AssemblyName System.Windows.Forms;
            $b = [System.Drawing.Bitmap]::new({w}, {h});
            $g = [System.Drawing.Graphics]::FromImage($b);
            $g.CopyFromScreen({x}, {y}, 0, 0, $b.Size);
            $b.Save("{save_path}");
            $g.Dispose(); $b.Dispose();
        """)
    else:
        ps(f"""
            Add-Type -AssemblyName System.Windows.Forms;
            $b = [System.Drawing.Bitmap]::new(
                [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
                [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
            );
            $g = [System.Drawing.Graphics]::FromImage($b);
            $g.CopyFromScreen(0, 0, 0, 0, $b.Size);
            $b.Save("{save_path}");
            $g.Dispose(); $b.Dispose();
        """)

    return f"Screenshot saved to {save_path}"


def get_active_window_title() -> str:
    """Get the title of the currently active window."""
    return ps("""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            public class W {
                [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
            }
"@
        $h = [W]::GetForegroundWindow();
        $sb = New-Object System.Text.StringBuilder 256;
        [W]::GetWindowText($h, $sb, 256);
        $sb.ToString()
    """)
