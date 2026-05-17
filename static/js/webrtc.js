/**
 * webrtc.js
 * - Xu ly ket noi WebRTC den camera Pi
 * - Ho tro 2 kieu: WebSocket signaling va HTTP offer/answer
 * KHONG chua HTML hay CSS
 */

var ketNoiWebRTC = null;   // RTCPeerConnection
var ketNoiWS = null;       // WebSocket den Pi
var dang_stream = false;

/**
 * Bat dau ket noi WebRTC den camera Pi.
 * @param {string} api_url - URL API cua Pi (ws:// hoac http://)
 * @param {HTMLVideoElement} phan_tu_video - Phan tu video de hien thi
 * @param {function} khi_thay_doi_trang_thai - Callback (trang_thai: string)
 */
function batDauWebRTC(api_url, phan_tu_video, khi_thay_doi_trang_thai) {
    if (dang_stream) dungWebRTC();

    khi_thay_doi_trang_thai('dang_ket_noi');

    // RTCPeerConnection voi STUN server cong cong
    var cau_hinh = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ]
    };

    ketNoiWebRTC = new RTCPeerConnection(cau_hinh);

    // Khi nhan duoc track video tu Pi
    ketNoiWebRTC.ontrack = function (su_kien) {
        if (su_kien.streams && su_kien.streams[0]) {
            phan_tu_video.srcObject = su_kien.streams[0];
            dang_stream = true;
            khi_thay_doi_trang_thai('da_ket_noi');
        }
    };

    // Xu ly ICE candidate
    ketNoiWebRTC.onicecandidate = function (su_kien) {
        if (su_kien.candidate && ketNoiWS && ketNoiWS.readyState === WebSocket.OPEN) {
            ketNoiWS.send(JSON.stringify({
                type: 'ice_candidate',
                candidate: su_kien.candidate
            }));
        }
    };

    ketNoiWebRTC.oniceconnectionstatechange = function () {
        var trang_thai = ketNoiWebRTC ? ketNoiWebRTC.iceConnectionState : '';
        if (trang_thai === 'disconnected' || trang_thai === 'failed' || trang_thai === 'closed') {
            khi_thay_doi_trang_thai('mat_ket_noi');
            dang_stream = false;
        }
    };

    // Quyet dinh kieu signaling dua tren URL
    if (api_url.startsWith('ws://') || api_url.startsWith('wss://')) {
        // Kieu 1: WebSocket signaling truc tiep voi Pi
        dungSignalingWS(api_url, khi_thay_doi_trang_thai);
    } else {
        // Kieu 2: HTTP offer/answer (Pi chay aiortc hoac tuong tu)
        dungSignalingHTTP(api_url, khi_thay_doi_trang_thai);
    }
}

/**
 * Signaling qua WebSocket truc tiep den Pi
 */
function dungSignalingWS(ws_url, khi_thay_doi_trang_thai) {
    try {
        ketNoiWS = new WebSocket(ws_url);

        ketNoiWS.onopen = function () {
            // Gui tin hieu san sang
            ketNoiWS.send(JSON.stringify({ type: 'ready' }));
        };

        ketNoiWS.onmessage = function (su_kien) {
            var tin = JSON.parse(su_kien.data);
            xuLyTinHieuNhanDuoc(tin, khi_thay_doi_trang_thai);
        };

        ketNoiWS.onerror = function () {
            khi_thay_doi_trang_thai('loi');
        };

        ketNoiWS.onclose = function () {
            if (dang_stream) khi_thay_doi_trang_thai('mat_ket_noi');
        };
    } catch (loi) {
        khi_thay_doi_trang_thai('loi');
    }
}

/**
 * Signaling qua HTTP: GET offer tu Pi, POST answer ve Pi
 */
function dungSignalingHTTP(http_url, khi_thay_doi_trang_thai) {
    var thong_tin_url = tachThongTinUrl(http_url);
    var url_thuần = thong_tin_url.url;
    var proxy_url = '/api/webrtc/http-proxy/';

    // Them transceivers de nhan video tu Pi
    ketNoiWebRTC.addTransceiver('video', { direction: 'recvonly' });
    ketNoiWebRTC.addTransceiver('audio', { direction: 'recvonly' });

    // Tao offer phia browser (se gui cho Pi)
    ketNoiWebRTC.createOffer()
        .then(function (offer) {
            return ketNoiWebRTC.setLocalDescription(offer);
        })
        .then(function () {
            // Cho ICE gathering xong roi moi gui
            return new Promise(function (resolve) {
                if (ketNoiWebRTC.iceGatheringState === 'complete') {
                    resolve();
                } else {
                    ketNoiWebRTC.onicegatheringstatechange = function () {
                        if (ketNoiWebRTC && ketNoiWebRTC.iceGatheringState === 'complete') resolve();
                    };
                }
            });
        })
        .then(function () {
            // Gui offer den Django proxy, proxy se forward sang Pi
            return fetch(proxy_url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (window.layCSRFToken ? window.layCSRFToken() : '')
                },
                body: JSON.stringify({
                    target_url: url_thuần,
                    username: thong_tin_url.username,
                    password: thong_tin_url.password,
                    sdp_offer: ketNoiWebRTC.localDescription.sdp
                })
            });
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { status: res.status, data: data };
            });
        })
        .then(function (ket_qua) {
            if (!ket_qua.data.thanh_cong) {
                throw new Error(ket_qua.data.loi || ('Proxy loi HTTP ' + ket_qua.status));
            }
            var sdp_answer = ket_qua.data.sdp_answer;
            if (!sdp_answer || !sdp_answer.trim()) {
                throw new Error('Proxy khong tra ve SDP answer');
            }
            var answer = { type: 'answer', sdp: sdp_answer };
            return ketNoiWebRTC.setRemoteDescription(new RTCSessionDescription(answer));
        })
        .catch(function (loi) {
            console.error('Loi ket noi WebRTC HTTP:', loi);
            var da_xu_ly = false;
            if (window.xuLyThatBaiWebRTCHTTP) {
                da_xu_ly = !!window.xuLyThatBaiWebRTCHTTP(loi, http_url);
            }
            if (!da_xu_ly && window.hienThiThongBao) {
                window.hienThiThongBao('Không thể kết nối stream: ' + loi.message, 'loi');
            }
            if (!da_xu_ly) {
                khi_thay_doi_trang_thai('loi');
            }
        });
}

/**
 * Tach URL va thong tin dang nhap neu co trong dang http://user:pass@host/path.
 */
function tachThongTinUrl(raw_url) {
    try {
        var parsed = new URL(raw_url);
        var username = parsed.username ? decodeURIComponent(parsed.username) : '';
        var password = parsed.password ? decodeURIComponent(parsed.password) : '';
        parsed.username = '';
        parsed.password = '';
        return {
            url: parsed.toString(),
            username: username,
            password: password
        };
    } catch (loi) {
        return { url: raw_url, username: '', password: '' };
    }
}

/**
 * Xu ly tin hieu nhan duoc tu Pi (qua WebSocket)
 */
function xuLyTinHieuNhanDuoc(tin, khi_thay_doi_trang_thai) {
    if (!ketNoiWebRTC) return;

    if (tin.type === 'offer') {
        ketNoiWebRTC.setRemoteDescription(new RTCSessionDescription(tin))
            .then(function () { return ketNoiWebRTC.createAnswer(); })
            .then(function (answer) { return ketNoiWebRTC.setLocalDescription(answer); })
            .then(function () {
                if (ketNoiWS && ketNoiWS.readyState === WebSocket.OPEN) {
                    ketNoiWS.send(JSON.stringify({
                        type: 'answer',
                        sdp: ketNoiWebRTC.localDescription.sdp
                    }));
                }
            });

    } else if (tin.type === 'answer') {
        ketNoiWebRTC.setRemoteDescription(new RTCSessionDescription(tin));

    } else if (tin.type === 'ice_candidate' && tin.candidate) {
        ketNoiWebRTC.addIceCandidate(new RTCIceCandidate(tin.candidate));
    }
}

/**
 * Dung stream WebRTC
 */
function dungWebRTC() {
    dang_stream = false;
    if (ketNoiWS) {
        ketNoiWS.close();
        ketNoiWS = null;
    }
    if (ketNoiWebRTC) {
        ketNoiWebRTC.close();
        ketNoiWebRTC = null;
    }
}

// Export ra window de chi_tiet_can.js su dung
window.batDauWebRTC = batDauWebRTC;
window.dungWebRTC = dungWebRTC;
