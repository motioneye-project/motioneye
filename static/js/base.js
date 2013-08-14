
function initUI() {
    $('input[type=checkbox].styled').each(function () {
        makeCheckBox($(this));
    });

//    $('select.styled').each(function () {
//        makeComboBox($(this));
//    });
    
    makeSlider($('#device-brightness'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#device-contrast'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#device-saturation'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#device-hue'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#device-framerate'), 1, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streaming-framerate'), 1, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streaming-quality'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#image-quality'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#movie-quality'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#motion-frame-change-threshold'), 0, 10000, 0, null, 3, 0, 'px');
    makeSlider($('#motion-noise-level'), 0, 100, 0, null, 5, 0, '%');
}

function handleDocumentReady() {
//    $('body').click(function () {
//        if ($('div.settings').hasClass('open')) {
//            $('div.settings').removeClass('open');
//            $('div.page-container').removeClass('stretched');
//        }
//        else {
//        }
//    });
//    
    $('div.settings').addClass('open');
    $('div.page-container').addClass('stretched');
    $('div.page').css('min-height', $('div.settings').height() + 100);
    
    initUI();
}
