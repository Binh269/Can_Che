document.addEventListener('DOMContentLoaded', function () {
    function thayBangIframeNeuKhongPhaiAnh(img) {
        var cell = img.closest('.camera-cell');
        if (!cell || cell.getAttribute('data-fallback-iframe') === '1') return;

        var url = cell.getAttribute('data-url') || img.getAttribute('src') || '';
        if (!url) return;

        cell.setAttribute('data-fallback-iframe', '1');
        var iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.setAttribute('frameborder', '0');
        iframe.setAttribute('allowfullscreen', 'allowfullscreen');
        img.replaceWith(iframe);
    }

    document.querySelectorAll('.camera-feed').forEach(function (img) {
        img.addEventListener('error', function () {
            thayBangIframeNeuKhongPhaiAnh(img);
        });
    });

    document.querySelectorAll('.camera-cell').forEach(function (cell) {
        cell.addEventListener('click', function () {
            var url = this.getAttribute('data-url') || '';
            if (!url) return;

            var modal = document.getElementById('modal-camera');
            var modalImg = document.getElementById('modal-camera-img');
            var modalIframe = document.getElementById('modal-camera-iframe');
            var dang_dung_iframe = this.getAttribute('data-fallback-iframe') === '1';

            if (!modal || !modalImg || !modalIframe) return;

            modalImg.src = '';
            modalIframe.src = '';
            if (dang_dung_iframe) {
                modalImg.style.display = 'none';
                modalIframe.style.display = 'block';
                modalIframe.src = url;
            } else {
                modalIframe.style.display = 'none';
                modalImg.style.display = 'block';
                modalImg.src = url;
            }
            modal.classList.add('hien');
        });
    });

    var modal = document.getElementById('modal-camera');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal || e.target.classList.contains('btn-dong')) {
                modal.classList.remove('hien');
                var modalImg = document.getElementById('modal-camera-img');
                var modalIframe = document.getElementById('modal-camera-iframe');
                if (modalImg) modalImg.src = '';
                if (modalIframe) modalIframe.src = '';
            }
        });
    }
});
