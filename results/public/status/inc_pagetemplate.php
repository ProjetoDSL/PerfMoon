<?php

$sOutMode=( (array_key_exists('format', $_GET) && $_GET['format']) ? 'data':'default');
    
$oLog->add('load '.$sOutMode.'/out_html.php ...');
// if (!include(__DIR__ . '/templates/' . $aEnv["active"]["skin"] . '/' . $aCfg['defaultTemplate'])) {
if (!include(__DIR__ . '/templates/'.$sOutMode.'/' . $aCfg['defaultTemplate'])) {
    // die('ERROR: Template could not be included: ' . './templates/' . $aCfg['skin'] . '/' . $aCfg['defaultTemplate'] . '.<br>Check the values "skin" and "defaultTemplate" in your configuration.');
    die('ERROR: Template could not be included: ' . './templates/'.$sOutMode.'/' . $aCfg['defaultTemplate'] . '.<br>Check the values "skin" and "defaultTemplate" in your configuration.');
}



$oPage->setAppDir($sSelfURL);

switch ($oPage->getOutputtype()) {
    case 'html':
        // v2.00.04
        $oPage->setContent($oDatarenderer->storeLocally($aSrvStatus).$oPage->getContent());
            
        // v1.13: version check

        
        $oPage->setReplacement('{{SKIN}}', $aEnv['active']['skin']);
        $oPage->setJsOnReady($sJsOnReady);
        $sHeader = $oPage->getHeader($sHead);
        if (!$aCfg["showHint"]) {
            $sHeader .= '<style>.hintbox{display: none;}</style>';
        }
        $sHeader .= getHtmlHead($aLangTxt);
        $oPage->setHeader($sHeader);

        break;
    default:
}