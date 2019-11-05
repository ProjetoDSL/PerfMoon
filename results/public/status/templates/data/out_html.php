<?php

$sFilter=false;
$sFormat='json';

// available formats and its MIME type
$aFormats=$oDatarenderer->getExportFormats();

// ======================================================================
// init
// ======================================================================


if (array_key_exists("filter", $_GET)){
    $sFilter=$_GET["filter"];
    $aFilters=$oDatarenderer->getValidFilters($aSrvStatus);
    if (!array_key_exists($sFilter, $aFilters)){
        die("ERROR: The filter $sFilter is not valid.");
    }
}
if (array_key_exists("format", $_GET)){
    $sFormat=$_GET["format"];
    if (!array_key_exists($sFormat, $aFormats)){
        die("ERROR: The format $sFormat is not valid.");
    }
}
$sExpFile='export_'.$aEnv["active"]["group"].'_'.$sFilter.'_'.date("Ymd_His").'.'.$aFormats[$sFormat]["ext"];


// ======================================================================
// get data
// ======================================================================


// TODO: demo mode for api to prevent public usage of the installation

if ($sFilter){
    if (array_key_exists("callfunction", $aFilters[$sFilter])){
        $aData=$oDatarenderer->{$aFilters[$sFilter]["callfunction"]}($aSrvStatus, false);
    } else {
        $aData = $oServerStatus->dataFilter($aSrvStatus,$aFilters[$sFilter]);
    }
} else {
    $aData = $aSrvStatus;
}



// ======================================================================
// 
// output
// 
// ======================================================================

$sBody=false;
switch ($sFormat) {
    case "csv":
        if (count($aData)){

            $outstream = fopen("php://memory", 'w+');
            
            // get teable header            
            fputcsv($outstream, array_keys($aData[0]));

            // loop over data rows
            foreach ($aData as $aRow){ 
                fputcsv($outstream, array_values($aRow));
            }
            
            rewind($outstream);
            $sBody = stream_get_contents($outstream);
            fclose($outstream);
        }
        break;
    case "json":
        $sBody=json_encode($aData);
        break;

    case "serialize":
        $sBody=serialize($aData);
        break;
    
    case "xml":
        require_once ('./classes/array2xml.class.php');
        $oXml = Array2XML::createXML('response', array('entry'=>$aData));
        $sBody=$oXml->saveXML();
        break;

    default:
        die("format $sFormat is not implemented (yet?).");
        break;
}

// ======================================================================
// put header and body to the page object
// ======================================================================

$oPage->setOutputtype("data");
$oPage->addResponseHeader("Content-Type: " . $aFormats[$sFormat]["mime"]);
$oPage->addResponseHeader('Content-Disposition: attachment; filename="'.$sExpFile.'"');
$oPage->setContent($sBody);
