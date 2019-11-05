<?php



$content=
    // $oDatarenderer->themeTable($aLangTxt["lblTable_status_workers"], $oDatarenderer->renderWorkersTable($aSrvStatus), $aLangTxt["lblTableHint_status_workers"]).
    // $oDatarenderer->renderTable('workers_table');
    $oDatarenderer->renderGroupAndServers($aSrvStatus).
    $oDatarenderer->renderWorkersTable($aSrvStatus).
    $oDatarenderer->renderTable('status');
