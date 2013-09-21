
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
    
    makeTimeValidator($('#mondayFrom'));
    makeTimeValidator($('#mondayTo'))
    makeTimeValidator($('#tuesdayFrom'));
    makeTimeValidator($('#tuesdayTo'))
    makeTimeValidator($('#wednesdayFrom'));
    makeTimeValidator($('#wednesdayTo'))
    makeTimeValidator($('#thursdayFrom'));
    makeTimeValidator($('#thursdayTo'))
    makeTimeValidator($('#fridayFrom'));
    makeTimeValidator($('#fridayTo'))
    makeTimeValidator($('#saturdayFrom'));
    makeTimeValidator($('#saturdayTo'))
    makeTimeValidator($('#sundayFrom'));
    makeTimeValidator($('#sundayTo'));
    
    $('#motionEyeSwitch').change(updateSettingsUI);
    $('#showAdvancedSwitch').change(updateSettingsUI);
    $('#storageDeviceSelect').change(updateSettingsUI);
    $('#autoBrightnessSwitch').change(updateSettingsUI);
    $('#leftTextSelect').change(updateSettingsUI);
    $('#rightTextSelect').change(updateSettingsUI);
    $('#captureModeSelect').change(updateSettingsUI);
    $('#autoNoiseDetectSwitch').change(updateSettingsUI);
    $('#videoDeviceSwitch').change(updateSettingsUI);
    $('#textOverlaySwitch').change(updateSettingsUI);
    $('#videoStreamingSwitch').change(updateSettingsUI);
    $('#stillImagesSwitch').change(updateSettingsUI);
    $('#motionMoviesSwitch').change(updateSettingsUI);
    $('#motionNotificationsSwitch').change(updateSettingsUI);
    $('#workingScheduleSwitch').change(updateSettingsUI);
}

function updateSettingsUI() {
    var objs = $('tr.settings-item, div.advanced-setting, table.advanced-setting, div.settings-section-title, table.settings');
    
    function markHide() {
        this._hide = true;
    }
    
    function unmarkHide() {
        this._hide = false;
    }
    
    objs.each(unmarkHide);
    
    /* general enable switch */
    var motionEyeEnabled = $('#motionEyeSwitch').get(0).checked;
    if (!motionEyeEnabled) {
        objs.not($('#motionEyeSwitch').parents('div').get(0)).each(markHide);
    }
    
    /* advanced settings */
    var showAdvanced = $('#showAdvancedSwitch').get(0).checked;
    if (!showAdvanced) {
        $('tr.advanced-setting, div.advanced-setting, table.advanced-setting').each(markHide);
    }
    
    /* storage device */
    if ($('#storageDeviceSelect').val() === 'local-disk') {
        $('#networkServerEntry').parents('tr:eq(0)').each(markHide);
        $('#networkUsernameEntry').parents('tr:eq(0)').each(markHide);
        $('#networkPasswordEntry').parents('tr:eq(0)').each(markHide);
        $('#networkShareNameEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* auto brightness */
    if ($('#autoBrightnessSwitch').get(0).checked) {
        $('#brightnessSlider').parents('tr:eq(0)').each(markHide);
    }
    
    /* text */
    if ($('#leftTextSelect').val() !== 'custom-text') {
        $('#leftTextEntry').parents('tr:eq(0)').each(markHide);
    }
    if ($('#rightTextSelect').val() !== 'custom-text') {
        $('#rightTextEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* still images capture mode */
    if ($('#captureModeSelect').val() !== 'interval-snapshots') {
        $('#snapshotIntervalEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* auto noise level */
    if ($('#autoNoiseDetectSwitch').get(0).checked) {
        $('#noiseLevelSlider').parents('tr:eq(0)').each(markHide);
    }
    
    /* video device switch */
    if (!$('#videoDeviceSwitch').get(0).checked) {
        $('#videoDeviceSwitch').parent().nextAll('div.settings-section-title, table.settings').each(markHide);
    }
    
    /* text overlay switch */
    if (!$('#textOverlaySwitch').get(0).checked) {
        $('#textOverlaySwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* video streaming switch */
    if (!$('#videoStreamingSwitch').get(0).checked) {
        $('#videoStreamingSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* still images switch */
    if (!$('#stillImagesSwitch').get(0).checked) {
        $('#stillImagesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* motion movies switch */
    if (!$('#motionMoviesSwitch').get(0).checked) {
        $('#motionMoviesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* motion notifications switch */
    if (!$('#motionNotificationsSwitch').get(0).checked) {
        $('#motionNotificationsSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* working schedule switch */
    if (!$('#workingScheduleSwitch').get(0).checked) {
        $('#workingScheduleSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    objs.each(function () {
        if (this._hide) {
            $(this).hide(200);
        }
        else {
            $(this).show(200);
        }
    });
}

$(document).ready(function () {
    /* open/close settings */
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
    
    /* prevent scroll events on settings div from propagating */
    $('div.settings').mousewheel(function (e, d) {
        var t = $(this);
        if (d > 0 && t.scrollTop() === 0) {
            e.preventDefault();
        }
        else if (d < 0 && (t.scrollTop() === t.get(0).scrollHeight - t.innerHeight())) {
            e.preventDefault();
        }
    });
    
    initUI();
    updateSettingsUI();
});
