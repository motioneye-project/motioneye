
$(window).on('load', function () {
    if (window.parent && window.parent.postMessage) {
        window.parent.postMessage({'hostname': hostname, 'version': version, 'url': window.location.href.replace('version/', '')}, '*');
    }
});
