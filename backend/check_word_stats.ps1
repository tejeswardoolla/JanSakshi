try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Open("C:\Users\TEJESWAR\Desktop\JanSakshi\JanSakshi_CodeForge_BuildX_2026_Project_Report.docx")
    $pages = $doc.ComputeStatistics(2) # 2 = wdStatisticPages
    $words = $doc.ComputeStatistics(0) # 0 = wdStatisticWords
    $doc.Close([ref]$false)
    $word.Quit()
    Write-Host "PAGES_RESULT:$pages"
    Write-Host "WORDS_RESULT:$words"
} catch {
    Write-Host "ERROR:$($_.Exception.Message)"
}

