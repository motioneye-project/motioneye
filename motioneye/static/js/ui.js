
var _modalDialogContexts = [];


    /* UI widgets */

function makeCheckBox($input) {
    $input.each(function () {
        var $this = $(this);

        var mainDiv = $('<div class="check-box"></div>');
        var buttonDiv = $('<div class="check-box-button"></div>');
        var text = $('<span class="check-box-text"><span>');

        function setOn() {
            text.html('<img src="' + staticPath + 'img/IEC5007_On_Symbol.svg" style="width:18px;height:18px;padding:2px">');
            mainDiv.addClass('on');
        }

        function setOff() {
            text.html('<img src="' + staticPath + 'img/IEC5008_Off_Symbol.svg" style="width:18px;height:18px;padding:2px">');
            mainDiv.removeClass('on');
        }

        buttonDiv.append(text);
        mainDiv.append(buttonDiv);

        /* transfer the CSS classes */
        mainDiv[0].className += ' ' + $this[0].className;

        /* add the element */
        $this.after(mainDiv);

        function update() {
            if ($this[0].checked) {
                setOn();
            }
            else {
                setOff();
            }
        }

        /* add event handers */
        $this.change(update).change();

        mainDiv.on('click', function () {
            $this[0].checked = !$this[0].checked;
            $this.change();
        });

        /* make the element focusable */
        mainDiv[0].tabIndex = 0;

        /* handle the key events */
        mainDiv.keydown(function (e) {
            if (e.which === 13 || e.which === 32) {
                $this[0].checked = !$this[0].checked;
                $this.change();

                return false;
            }
        });

        this.update = update;
    });
}

function makeSlider($input, minVal, maxVal, snapMode, ticks, ticksNumber, decimals, unit) {
    unit = unit || '';

    $input.each(function () {
        var $this = $(this);
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

        var adjusting = false;

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
            $this.val(val.toFixed(decimals));
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
            adjusting = false;

            $this.change();
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
            adjusting = true;

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
            var value = parseFloat($this.val());
            if (isNaN(value)) {
                value = minVal;
            }

            var pos = valToPos(value);
            pos = bestPos(pos);
            cursor.css('left', pos + '%');
            cursorLabel.html(value.toFixed(decimals) + unit);
        }

        /* show / hide cursor label tooltip */
        cursor.mouseenter(function (e) {
            if (!adjusting) {
                cursorLabel.css('display', 'inline-block');
            }
        });
        cursor.mouseleave(function (e) {
            if (!adjusting) {
                cursorLabel.css('display', 'none');
            }
        });

        /* transfer the CSS classes */
        slider.addClass($this.attr('class'));

        /* handle input events */
        $this.change(input2slider).change();

        /* add the slider to the parent of the input */
        $this.after(slider);

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
                        var val = Math.max(minVal, parseFloat($this.val()) - step);
                        if (decimals == 0) {
                            val = Math.floor(val);
                        }

                        var origSnapMode = snapMode;
                        snapMode = 0;
                        $this.val(val).change();
                        snapMode = origSnapMode;
                    }

                    break;

                case 39: /* right */
                    if (snapMode == 1) { /* strict snapping */
                        // TODO implement me
                    }
                    else {
                        var step = (maxVal - minVal) / 200;
                        var val = Math.min(maxVal, parseFloat($this.val()) + step);
                        if (decimals == 0) {
                            val = Math.ceil(val);
                        }

                        var origSnapMode = snapMode;
                        snapMode = 0;
                        $this.val(val).change();
                        snapMode = origSnapMode;
                    }

                    break;
            }
        });

        this.update = input2slider;

        slider[0].setMinVal = function (mv) {
            minVal = mv;

            makeTicks();
        };

        slider[0].setMaxVal = function (mv) {
            maxVal = mv;

            makeTicks();

            input2slider();
        };
    });
}

function makeProgressBar($div) {
    $div.each(function () {
        var $this = $(this);

        $this.addClass('progress-bar-container');
        var fillDiv = $('<div class="progress-bar-fill"></div>');
        var textSpan = $('<span class="progress-bar-text"></span>');

        $this.append(fillDiv);
        $this.append(textSpan);

        this.setProgress = function (progress) {
            $this.progress = progress;
            fillDiv.width(progress + '%');
        };

        this.setText = function (text) {
            textSpan.html(text);
        };
    });
}


    /* validators */

function makeTextValidator($input, required) {
    if (required == null) {
        required = true;
    }

    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            if (strVal.length === 0 && required) {
                return false;
            }

            return true;
        }

        var msg = i18n.gettext("Ĉi tiu kampo estas deviga");

        function validate() {
            var strVal = $this.val();
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('text-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });
}

function makeComboValidator($select, required) {
    if (required == null) {
        required = true;
    }

    $select.each(function () {
        $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            if (strVal.length === 0 && required) {
                return false;
            }

            return true;
        }

        var msg = i18n.gettext("Ĉi tiu kampo estas deviga");

        function validate() {
            var strVal = $this.val() || '';
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('combo-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
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

    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
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
	if (!sign && floating)
            msg = i18n.gettext("enigu pozitivan nombron");
	else if (!sign && !floating)
            msg = i18n.gettext("enigu pozitivan entjeran nombron");
	else if (sign && floating)
            msg = i18n.gettext("enigu nombron");
	else
            msg = i18n.gettext("enigu entjeran nombron");
        if (isFinite(minVal)) {
            if (isFinite(maxVal)) {
                msg += i18n.gettext(" inter ") + minVal + i18n.gettext(" kaj ") + maxVal;
            }
            else {
                msg += i18n.gettext(" pli ol ") + minVal;
            }
        }
        else {
            if (isFinite(maxVal)) {
                msg += i18n.gettext(" malpli ol ") + maxVal;
            }
        }

        function validate() {
            var strVal = $this.val();
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('number-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });

    makeStrippedInput($input);
}

function makeTimeValidator($input) {
    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            return strVal.match(new RegExp('^[0-2][0-9]:[0-5][0-9]$')) != null;
        }

        var msg = i18n.gettext("enigu validan tempon en la sekva formato: HH:MM");

        function validate() {
            var strVal = $this.val();
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.timepicker({
            closeOnWindowScroll: true,
            selectOnBlur: true,
            timeFormat: 'H:i',
        });

        $this.addClass('validator');
        $this.addClass('time-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });

    makeStrippedInput($input);
}

function makeUrlValidator($input) {
    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            return strVal.match(new RegExp('^([a-zA-Z]+)://([\\w\-.]+)(:\\d+)?(/.*)?$')) != null;
        }

        var msg = i18n.gettext("enigu validan URL (ekz. http://ekzemplo.com:8080/cams/)");

        function validate() {
            var strVal = $this.val();
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('url-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });
}

function makeFileValidator($input, required) {
    if (required == null) {
        required = true;
    }

    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            if (strVal.length === 0 && required) {
                return false;
            }

            return true;
        }

        var msg = i18n.gettext("Ĉi tiu kampo estas deviga");

        function validate() {
            var strVal = $this.val();
            if (isValid(strVal)) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', msg);
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('file-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }
                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });
}

function makeCustomValidator($input, isValidFunc) {
    $input.each(function () {
        var $this = $(this);

        function isValid(strVal) {
            if (!$this.is(':visible')) {
                return true; /* an invisible element is considered always valid */
            }

            return isValidFunc(strVal);
        }

        function validate() {
            var strVal = $this.val();
            var valid = isValid(strVal);
            if (valid == true) {
                $this.attr('title', '');
                $this.removeClass('error');
                $this[0].invalid = false;
            }
            else {
                $this.attr('title', valid || 'enter a valid value');
                $this.addClass('error');
                $this[0].invalid = true;
            }
        }

        $this.addClass('validator');
        $this.addClass('custom-validator');
        $this.each(function () {
            var oldValidate = this.validate;
            this.validate = function () {
                if (oldValidate) {
                    if (!oldValidate.call(this)) {
                        return;
                    }
                }

                validate();
                return !this.invalid;
            }
        });

        $this.keyup(function () {this.validate();});
        $this.blur(function () {this.validate();});
        $this.change(function () {this.validate();}).change();
    });
}


    /* other input value processors */

function makeStrippedInput($input) {
    $input.change(function () {
        this.value = $.trim(this.value);
    });
}

function makeCharReplacer($input, oldChars, newStr) {
    $input.change(function () {
        this.value = this.value.replace(new RegExp('[' + oldChars + ']', 'g'), newStr);
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
        modalWidth = container.outerWidth();
        modalHeight = container.outerHeight();

        container.css('left', Math.floor((windowWidth - modalWidth) / 2));
        container.css('top', Math.floor((windowHeight - modalHeight) / 2));
    }
}

function makeModalDialogButtons(buttonsInfo) {
    /* buttonsInfo is an array of:
     * * caption: String
     * * isDefault: Boolean
     * * click: Function
     * * className: String
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
                    return false;
                }

                hideModalDialog();

                return false;
            };
        }
        else {
            info.click = hideModalDialog; /* every button closes the dialog */
        }

        if (info.className) {
            buttonDiv.addClass(info.className);
        }

        buttonDiv.on('click', info.click);

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
        titleSpan.css('margin', '0px 2em');
    }

    titleBar.append(titleSpan);

    if (options.closeButton) {
        var closeButton = $('<div class="button icon modal-close-button mouse-effect" title="'+i18n.gettext("fermi")+'"></div>');
        closeButton.on('click', hideModalDialog);
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
     * * noKeys: Boolean
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
            {caption: i18n.gettext("Ne"), click: options.onNo},
            {caption: i18n.gettext("Jes"), isDefault: true, click: options.onYes}
        ];
    }
    if (options.buttons === 'yesnocancel') {
        options.buttons = [
            {caption: i18n.gettext("Nuligi"), isCancel: true, click: options.onCancel},
            {caption: i18n.gettext("Ne"), click: options.onNo},
            {caption: i18n.gettext("Jes"), isDefault: true, click: options.onYes}
        ];
    }
    else if (options.buttons === 'okcancel') {
        options.buttons = [
            {caption: i18n.gettext("Nuligi"), isCancel:true, click: options.onCancel},
            {caption: i18n.gettext("Bone"), isDefault: true, click: options.onOk}
        ];
    }
    else if (options.buttons === 'ok') {
        options.buttons = [
            {caption: i18n.gettext("Bone"), isDefault: true, click: options.onOk}
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

    var handleKeyUp = !options.noKeys && function (e) {
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
