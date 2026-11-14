try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Open("C:\Users\TEJESWAR\Desktop\JanSakshi\JanSakshi_CodeForge_BuildX_2026_Project_Report.docx")
    foreach ($p in $doc.Paragraphs) {
        $text = $p.Range.Text.Trim()
        if ($text -match "^(Table of Contents|Abstract|1\.|2\.|3\.|4\.|5\.|6\.|7\.|8\.|9\.|10\.)") {
            $page = $p.Range.Information(3) # 3 = wdActiveEndPageNumber
            Write-Host "HEADING: '$text' on Page $page"
        }
    }
    $doc.Close([ref]$false)
    $word.Quit()
} catch {
    Write-Host "ERROR:$($_.Exception.Message)"
}

