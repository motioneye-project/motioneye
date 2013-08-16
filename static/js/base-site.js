
function initUI() {
    $('input[type=checkbox].styled').each(function () {
        makeCheckBox($(this));
    });

    makeSlider($('#brightnessSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#contrastSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#saturationSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#hueSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#framerateSlider'), 1, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streamingFramerateSlider'), 1, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streamingQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#imageQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#movieQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#frameChangeThresholdSlider'), 0, 10000, 0, null, 3, 0, 'px');
    makeSlider($('#noiseLevelSlider'), 0, 100, 0, null, 5, 0, '%');
    
    makeNumberValidator($('#snapshotIntervalEntry'), 1, 86400, false, false);
    makeNumberValidator($('#gapEntry'), 1, 86400, false, false);
    makeNumberValidator($('#preCaptureEntry'), 0, 100, false, false);
    makeNumberValidator($('#postCaptureEntry'), 0, 100, false, false);
}

$(document).ready(function () {
    $('img.settings-button').click(function () {
        if ($('div.settings').hasClass('open')) {
            $('div.settings').removeClass('open');
            $('div.page-container').removeClass('stretched');
            $('div.settings-top-bar').removeClass('open');
        }
        else {
            $('div.settings').addClass('open');
            $('div.page-container').addClass('stretched');
            $('div.settings-top-bar').addClass('open');
        }
    });
    
    initUI();
});
