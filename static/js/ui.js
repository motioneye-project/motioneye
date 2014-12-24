
var _modalDialogContexts = [];


    /* UI widgets */

function makeCheckBox($input) {
    var mainDiv = $('<div class="check-box"></div>');
    var buttonDiv = $('<div class="check-box-button"></div>');
    var text = $('<span class="check-box-text"><span>');
    
    function setOn() {
        text.html('ON');
        mainDiv.addClass('on');
    }
    
    function setOff() {
        text.html('OFF');
        mainDiv.removeClass('on');
    }
    
    buttonDiv.append(text);
    mainDiv.append(buttonDiv);
    
    /* transfer the CSS classes */
    mainDiv[0].className += ' ' + $input[0].className;
    
    /* add the element */
    $input.after(mainDiv);
    
    function update() {
        if ($input[0].checked) {
            setOn();
        }
        else {
            setOff();
        }
    }
    
    /* add event handers */
    $input.change(update).change();
    
    mainDiv.click(function () {
        $input[0].checked = !$input[0].checked;
        $input.change();
    });
    
    /* make the element focusable */
    mainDiv[0].tabIndex = 0;
    
    /* handle the key events */
    mainDiv.keydown(function (e) {
        if (e.which === 13 || e.which === 32) {
            $input[0].checked = !$input[0].checked;
            $input.change();
            
            return false;
        }
    });
    
    $input[0].update = update;
    
    return mainDiv;
}

function makeSlider($input, minVal, maxVal, snapMode, ticks, ticksNumber, decimals, unit) {
    unit = unit || '';
    
    var slider = $('<div class="slider"></div>');
    
    var labels = $('<div class="slider-labels"></div>');
    slider.append(labels);
    
    var bar = $('<div class="slider-bar"></div>');
    slider.append(bar);
    
    bar.append('<div class="slider-bar-inside"></div>');
    
    var cursor = $('<div class="slider-cursor"></div>');
    bar.append(cursor);
    
    var cursorLabel = $('<div class="slider-cursor-label"></div>');
    cursor.append(cursorLabel);
    
    function bestPos(pos) {
        if (pos < 0) {
            pos = 0;
        }
        if (pos > 100) {
            pos = 100;
        }
        
        if (snapMode > 0) {
            var minDif = Infinity;
            var bestPos = null;
            for (var i = 0; i < ticks.length; i++) {
                var tick = ticks[i];
                var p = valToPos(tick.value);
                var dif = Math.abs(p - pos);
                if ((dif < minDif) && (snapMode == 1 || dif < 5)) {
                    minDif = dif;
                    bestPos = p;
                }
            }
            
            if (bestPos != null) {
                pos = bestPos;
            }
        }
        
        return pos;
    }
    
    function getPos() {
        return parseInt(cursor.position().left * 100 / bar.width());
    }
    
    function valToPos(val) {
        return (val - minVal) * 100 / (maxVal - minVal);
    }
    
    function posToVal(pos) {
        return minVal + pos * (maxVal - minVal) / 100;
    }
    
    function sliderChange(val) {
        $input.val(val.toFixed(decimals));
        cursorLabel.html('' + val.toFixed(decimals) + unit);
    }
    
    function bodyMouseMove(e) {
        if (bar[0]._mouseDown) {
            var offset = bar.offset();
            var pos = e.pageX - offset.left - 5;
            pos = pos / slider.width() * 100;
            pos = bestPos(pos);
            var val = posToVal(pos);
            
            cursor.css('left', pos + '%');
            sliderChange(val);
        }
    }
    
    function bodyMouseUp(e) {
        bar[0]._mouseDown = false;

        $('body').unbind('mousemove', bodyMouseMove);
        $('body').unbind('mouseup', bodyMouseUp);
        
        cursorLabel.css('display', 'none');
        
        $input.change();
    }
    
    bar.mousedown(function (e) {
        if (e.which > 1) {
            return;
        }
        
        this._mouseDown = true;
        bodyMouseMove(e);

        $('body').mousemove(bodyMouseMove);
        $('body').mouseup(bodyMouseUp);
        
        slider.focus();
        cursorLabel.css('display', 'inline-block');
        
        return false;
    });
    
    /* ticks */
    var autoTicks = (ticks == null);
    
    function makeTicks() {
        if (ticksNumber == null) {
            ticksNumber = 11; 
        }

        labels.html('');
        
        if (autoTicks) {
            ticks = [];
            var i;
            for (i = 0; i < ticksNumber; i++) {
                var val = minVal + i * (maxVal - minVal) / (ticksNumber - 1);
                var valStr;
                if (Math.round(val) == val) {
                    valStr = '' + val;
                }
                else {
                    valStr = val.toFixed(decimals);
                }
                ticks.push({value: val, label: valStr + unit});
            }
        }
        
        for (i = 0; i < ticks.length; i++) {
            var tick = ticks[i];
            var pos = valToPos(tick.value);
            var span = $('<span class="slider-label" style="left: -9999px;">' + tick.label + '</span>');
            
            labels.append(span);
            span.css('left', (pos - 10) + '%');
        }
        
        return ticks;
    }
    
    makeTicks();

    function input2slider() {
        var value = parseFloat($input.val());
        if (isNaN(value)) {
            value = minVal;
        }
        
        var pos = valToPos(value);
        pos = bestPos(pos);
        cursor.css('left', pos + '%');
        cursorLabel.html($input.val() + unit);
    }
    
    /* transfer the CSS classes */
    slider.addClass($input.attr('class'));
    
    /* handle input events */
    $input.change(input2slider).change();
    
    /* add the slider to the parent of the input */
    $input.after(slider);
    
    /* make the slider focusable */
    slider.attr('tabIndex', 0);
    
    /* handle key events */
    slider.keydown(function (e) {
        switch (e.which) {
            case 37: /* left */
                if (snapMode == 1) { /* strict snapping */
                    // TODO implement me
                }
                else {
                    var step = (maxVal - minVal) / 200;
                    var val = Math.max(minVal, parseFloat($input.val()) - step);
                    if (decimals == 0) {
                        val = Math.floor(val);
                    }
                    
                    var origSnapMode = snapMode;
                    snapMode = 0;
                    $input.val(val).change();
                    snapMode = origSnapMode;
                }
                
                break;
                
            case 39: /* right */
                if (snapMode == 1) { /* strict snapping */
                    // TODO implement me
                }
                else {
                    var step = (maxVal - minVal) / 200;
                    var val = Math.min(maxVal, parseFloat($input.val()) + step);
                    if (decimals == 0) {
                        val = Math.ceil(val);
                    }

                    var origSnapMode = snapMode;
                    snapMode = 0;
                    $input.val(val).change();
                    snapMode = origSnapMode;
                }
                
                break;
        }
    });
    
    $input.each(function () {
        this.update = input2slider;
    });
    
    slider.setMinVal = function (mv) {
        minVal = mv;

        makeTicks();
    };
    
    slider.setMaxVal = function (mv) {
        maxVal = mv;

        makeTicks();
        
        input2slider();
    };
    
    return slider;
}


    /* validators */

function makeTextValidator($input, required) {
    if (required == null) {
        required = true;
    }
    
    function isValid(strVal) {
        if (!$input.is(':visible')) {
            return true; /* an invisible element is considered always valid */
        }
        
        if (strVal.length === 0 && required) {
            return false;
        }

        return true;
    }
    
    var msg = 'this field is required';
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
            $input[0].invalid = false;
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
            $input[0].invalid = true;
        }
    }
    
    $input.keyup(validate);
    $input.blur(validate);
    $input.change(validate).change();
    
    $input.addClass('validator');
    $input.addClass('text-validator');
    $input.each(function () {
        this.validate = validate;
    });
}

function makeComboValidator($select, required) {
    if (required == null) {
        required = true;
    }
    
    function isValid(strVal) {
        if (!$select.is(':visible')) {
            return true; /* an invisible element is considered always valid */
        }
        
        if (strVal.length === 0 && required) {
            return false;
        }

        return true;
    }
    
    var msg = 'this field is required';
    
    function validate() {
        var strVal = $select.val() || '';
        if (isValid(strVal)) {
            $select.attr('title', '');
            $select.removeClass('error');
            $select[0].invalid = false;
        }
        else {
            $select.attr('title', msg);
            $select.addClass('error');
            $select[0].invalid = true;
        }
    }
    
    $select.keyup(validate);
    $select.blur(validate);
    $select.change(validate).change();
    
    $select.addClass('validator');
    $select.addClass('combo-validator');
    $select.each(function () {
        this.validate = validate;
    });
}

function makeNumberValidator($input, minVal, maxVal, floating, sign, required) {
    if (minVal == null) {
        minVal = -Infinity;
    }
    if (maxVal == null) {
        maxVal = Infinity;
    }
    if (floating == null) {
        floating = false;
    }
    if (sign == null) {
        sign = false;
    }
    if (required == null) {
        required = true;
    }
    
    function isValid(strVal) {
        if (!$input.is(':visible')) {
            return true; /* an invisible element is considered always valid */
        }

        if (strVal.length === 0 && !required) {
            return true;
        }
        
        var numVal = parseInt(strVal);
        if ('' + numVal != strVal) {
            return false;
        }
        
        if (numVal < minVal || numVal > maxVal) {
            return false;
        }
        
        if (!sign && numVal < 0) {
            return false;
        }
        
        return true;
    }
    
    var msg = '';
    if (!sign) {
        msg = 'enter a positive';
    }
    else {
        msg = 'enter a';
    }
    if (floating) {
        msg += ' number';
    }
    else {
        msg += ' integer number';
    }
    if (isFinite(minVal)) {
        if (isFinite(maxVal)) {
            msg += ' between ' + minVal + ' and ' + maxVal;
        }
        else {
            msg += ' greater than ' + minVal;
        }
    }
    else {
        if (isFinite(maxVal)) {
            msg += ' smaller than ' + maxVal;
        }
    }
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
            $input[0].invalid = false;
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
            $input[0].invalid = true;
        }
    }
    
    $input.keyup(validate);
    $input.blur(validate);
    $input.change(validate).change();
    
    $input.addClass('validator');
    $input.addClass('number-validator');
    $input.each(function () {
        this.validate = validate;
    });
}

function makeTimeValidator($input) {
    function isValid(strVal) {
        if (!$input.is(':visible')) {
            return true; /* an invisible element is considered always valid */
        }

        return strVal.match(new RegExp('^[0-2][0-9]:[0-5][0-9]$')) != null;
    }
    
    var msg = 'enter a valid time in the following format: HH:MM';
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
            $input[0].invalid = false;
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
            $input[0].invalid = true;
        }
    }
    
    $input.keyup(validate);
    $input.blur(validate);
    $input.change(validate).change();
    $input.timepicker({
        closeOnWindowScroll: true,
        selectOnBlur: true,
        timeFormat: 'H:i',
    });
    
    $input.addClass('validator');
    $input.addClass('time-validator');
    $input.each(function () {
        this.validate = validate;
    });
}

function makeUrlValidator($input) {
    function isValid(strVal) {
        if (!$input.is(':visible')) {
            return true; /* an invisible element is considered always valid */
        }

        return strVal.match(new RegExp('^([a-zA-Z]+)://([\\w\-.]+)(:\\d+)?(/.*)?$')) != null;
    }
    
    var msg = 'enter a valid URL (e.g. http://example.com:8080/cams/)';
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
            $input[0].invalid = false;
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
            $input[0].invalid = true;
        }
    }
    
    $input.keyup(validate);
    $input.blur(validate);
    $input.change(validate).change();
    
    $input.addClass('validator');
    $input.addClass('url-validator');
    $input.each(function () {
        this.validate = validate;
    });
}


    /* modal dialog */

function showModalDialog(content, onClose, onShow, stack) {
    var glass = $('div.modal-glass');
    var container = $('div.modal-container');
    
    if (container.is(':animated')) {
        return setTimeout(function () {
            showModalDialog(content, onClose, onShow, stack);
        }, 100);
    }
    
    if (container.is(':visible') && stack) {
        /* the modal dialog is already visible,
         * we just replace the content */
        
        var children = container.children(':visible');
        _modalDialogContexts.push({
            children: children,
            onClose: container[0]._onClose,
        });
        
        children.css('display', 'none');
        updateModalDialogPosition();
        
        container[0]._onClose = onClose; /* set the new onClose handler */
        container.append(content);
        updateModalDialogPosition();
        
        if (onShow) {
            onShow();
        }
        
        return;
    }
    
    glass.css('display', 'block');
    glass.animate({'opacity': '0.7'}, 200);
    
    container[0]._onClose = onClose; /* remember the onClose handler */
    container.html(content);
    
    container.css('display', 'block');
    updateModalDialogPosition();
    container.animate({'opacity': '1'}, 200);
    
    if (onShow) {
        onShow();
    }
}

function hideModalDialog() {
    var glass = $('div.modal-glass');
    var container = $('div.modal-container');
    
    if (container.is(':animated')) {
        return setTimeout(function () {
            hideModalDialog();
        }, 100);
    }
    
    if (_modalDialogContexts.length) {
        if (container[0]._onClose) {
            container[0]._onClose();
        }
        
        container.children(':visible').remove();
        
        var context = _modalDialogContexts.pop();
        context.children.css('display', '');
        container[0]._onClose = context.onClose;
        updateModalDialogPosition();
        
        return;
    }
    
    glass.animate({'opacity': '0'}, 200, function () {
        glass.css('display', 'none');
    });
    
    container.animate({'opacity': '0'}, 200, function () {
        container.css('display', 'none');
        container.html('');
    });
    
    /* run the onClose handler, if supplied */
    if (container[0]._onClose) {
        container[0]._onClose();
    }
}

function updateModalDialogPosition() {
    var container = $('div.modal-container');
    if (!container.is(':visible')) {
        return;
    }
    
    var windowWidth = $(window).width();
    var windowHeight = $(window).height();
    var modalWidth, modalHeight, i;
    
    /* repeat the operation multiple times, the size might change */
    for (i = 0; i < 3; i++) {
        modalWidth = container.outerWidth() + 10 /* the margins */;
        modalHeight = container.outerHeight() + 10 /* the margins */;
        
        container.css('left', Math.floor((windowWidth - modalWidth) / 2));
        container.css('top', Math.floor((windowHeight - modalHeight) / 2));
    }
}

function makeModalDialogButtons(buttonsInfo) {
    /* buttonsInfo is an array of:
     * * caption: String
     * * isDefault: Boolean
     * * click: Function
     */
    
    var buttonsContainer = $('<table class="modal-buttons-container"><tr></tr></table>');
    var tr = buttonsContainer.find('tr');
    
    buttonsInfo.forEach(function (info) {
        var buttonDiv = $('<div class="button dialog mouse-effect"></div>');
        
        buttonDiv.attr('tabIndex', '0'); /* make button focusable */
        buttonDiv.html(info.caption);
        
        if (info.isDefault) {
            buttonDiv.addClass('default');
        }
        
        if (info.click) {
            var oldClick = info.click;
            info.click = function () {
                if (oldClick() == false) {
                    return;
                }
                
                hideModalDialog();
                
                return false;
            };
        }
        else {
            info.click = hideModalDialog; /* every button closes the dialog */
        }
        
        buttonDiv.click(info.click);

        var td = $('<td></td>');
        td.append(buttonDiv);
        tr.append(td);
    });
    
    /* limit the size of the buttons container */
    buttonsContainer.css('max-width', (buttonsInfo.length * 10) + 'em');
    
    return buttonsContainer;
}

function makeModalDialogTitleBar(options) {
    /* available options:
     * * title: String
     * * closeButton: Boolean
     */
    
    var titleBar = $('<div class="modal-title-bar"></div>');
    
    var titleSpan = $('<span class="modal-title"></span>');
    titleSpan.html(options.title || '');
    if (options.closeButton) {
        titleSpan.css('margin', '0px 1.5em');
    }
    
    titleBar.append(titleSpan);
    
    if (options.closeButton) {
        var closeButton = $('<div class="button modal-close-button mouse-effect" title="close"></div>');
        closeButton.click(hideModalDialog);
        titleBar.append(closeButton);
    }
    
    return titleBar;
}

function runModalDialog(options) {
    /* available options:
     * * title: String
     * * closeButton: Boolean
     * * content: any
     * * buttons: 'ok'|'yesno'|'okcancel'|Array
     * * onYes: Function
     * * onNo: Function
     * * onOk: Function
     * * onCancel: Function
     * * onClose: Function
     * * onShow: Function
     * * stack: Boolean
     */
    
    var content = $('<div></div>');
    var titleBar = null;
    var buttonsDiv = null;
    var defaultClick = null;
    var cancelClick = null;
    
    /* add title bar */
    if (options.title) {
        titleBar = makeModalDialogTitleBar({title: options.title, closeButton: options.closeButton});
        content.append(titleBar);
    }
    
    /* add supplied content */
    if (options.content) {
        var contentWrapper = $('<div style="padding: 10px;"></div>');
        contentWrapper.append(options.content);
        content.append(contentWrapper);
    }
    
    /* add buttons */
    if (options.buttons === 'yesno') {
        options.buttons = [
            {caption: 'No', click: options.onNo},
            {caption: 'Yes', isDefault: true, click: options.onYes}
        ];
    }
    if (options.buttons === 'yesnocancel') {
        options.buttons = [
            {caption: 'Cancel', isCancel: true, click: options.onCancel},
            {caption: 'No', click: options.onNo},
            {caption: 'Yes', isDefault: true, click: options.onYes}
        ];
    }
    else if (options.buttons === 'okcancel') {
        options.buttons = [
            {caption: 'Cancel', isCancel:true, click: options.onCancel},
            {caption: 'OK', isDefault: true, click: options.onOk}
        ];
    }
    else if (options.buttons === 'ok') {
        options.buttons = [
            {caption: 'OK', isDefault: true, click: options.onOk}
        ];
    }
    
    if (options.buttons) {
        buttonsDiv = makeModalDialogButtons(options.buttons);
        content.append(buttonsDiv);
        
        options.buttons.forEach(function (info) {
            if (info.isDefault) {
                defaultClick = info.click;
            }
            else if (info.isCancel) {
                cancelClick = info.click;
            }
        });
    }
    
    /* add some margins */
    if ((buttonsDiv || options.content) && titleBar) {
        titleBar.css('margin-bottom', '5px');
    }
    
    if (buttonsDiv && options.content) {
        buttonsDiv.css('margin-top', '5px');
    }
    
    var handleKeyUp = function (e) {
        if (!content.is(':visible')) {
            return;
        }
        
        switch (e.which) {
            case 13:
                if (defaultClick && defaultClick() == false) {
                    return;
                }
                
                hideModalDialog();
                
                break;
           
            case 27:
                if (cancelClick && cancelClick() == false) {
                    return;
                }

                hideModalDialog();

                break;
        }
    };
    
    var onClose = function () {
        if (options.onClose) {
            options.onClose();
        }
        
        /* unbind html handlers */
        
        $('html').unbind('keyup', handleKeyUp);
    };
    
    /* bind key handlers */
    $('html').bind('keyup', handleKeyUp);
    
    /* and finally, show the dialog */

    showModalDialog(content, onClose, options.onShow, options.stack);
    
    /* focus the default button if nothing else is focused */
    if (content.find('*:focus').length === 0) {
        content.find('div.button.default').focus();
    }
}


    /* popup message */

function showPopupMessage(message, type) {
    var container = $('div.popup-message-container');
    var content = $('<span class="popup-message"></span>');
    
    if (window._popupMessageTimeout) {
        clearTimeout(window._popupMessageTimeout);
    }
    
    content.html(message);
    content.addClass(type);
    container.html(content);
    
    var windowWidth = $(window).width();
    var messageWidth = container.width();
    
    container.css('display', 'block');
    container.css('left', (windowWidth - messageWidth) / 2);

    container.animate({'opacity': '1'}, 200);
    
    window._popupMessageTimeout = setTimeout(function () {
        window._popupMessageTimeout = null;
        container.animate({'opacity': '0'}, 200, function () {
            container.css('display', 'none');
        });
    }, 5000);
}
