import json
from channels.generic.websocket import AsyncWebsocketConsumer


class SignalingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer de lam trung gian tin hieu WebRTC (signaling).
    Dung cho truong hop Pi khong expose truc tiep ra ngoai.
    Group name = camera_<camera_id>, cac peer cung camera se cung group.
    """

    async def connect(self):
        self.camera_id = self.scope['url_route']['kwargs']['camera_id']
        self.group_name = f"camera_{self.camera_id}"

        # Tham gia vao group cua camera
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, ma_loi):
        # Roi khoi group khi ngat ket noi
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Nhan tin hieu tu client (offer, answer, ice_candidate).
        Chuyen tiep den tat ca thanh vien khac trong group.
        """
        try:
            du_lieu = json.loads(text_data)
            loai_tin = du_lieu.get('type', '')

            # Chuyen tiep tin hieu den cac peer khac
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chuyen_tiep_tin_hieu',
                    'du_lieu': du_lieu,
                    'nguon': self.channel_name,  # De tranh gui lai cho chinh minh
                }
            )
        except json.JSONDecodeError:
            pass

    async def chuyen_tiep_tin_hieu(self, event):
        """Nhan su kien tu group va gui ve client (tru nguon)."""
        # Khong gui lai cho chinh peer da gui
        if event['nguon'] == self.channel_name:
            return

        await self.send(text_data=json.dumps(event['du_lieu']))
