import pygame
import sys
from pygame import transform as pg_transform
import math
import random
# =========================================================
# 1. 기본 설정 & 전역 상수
# =========================================================

pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
pygame.init()
WIDTH, HEIGHT = 800, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("BJC - Badminton Junkies Crew")
clock = pygame.time.Clock()
FPS = 60

# 색/폰트
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY  = (200, 200, 200)
PRIMARY = (30, 144, 255)
RED = (220, 40, 40)
GREEN = (40, 160, 60)

FONT_L = pygame.font.SysFont("malgungothic", 48)  # 한글 폰트(윈도우 기준)
FONT_M = pygame.font.SysFont("malgungothic", 28)
FONT_S = pygame.font.SysFont("malgungothic", 22)

# === 규칙 상수 (섹션 1 아래에 추가) ===
ENABLE_TIME_LIMIT = True   # 시간 제한 사용 여부
ROUND_TIME        = 60     # 라운드 시간(초). 0이면 무제한
TARGET_SCORE      = 21      # 목표 점수
TWO_POINT_RULE    = False  # 2점 차 규칙 사용 여부

# === 물리/조작 상수 ===
ACCEL_PER_KEY = 30.0       # (이전 버전: 셔틀 가속) — 이제는 셔틀 직접 가속 대신 라켓 타격으로만 반영
MAX_SPEED_SHUTTLE = 520.0  # 셔틀 최대 속도(픽셀/초)
FRICTION_SHUTTLE  = 0.995  # 셔틀 공기저항(가벼운 감속)

PLAYER_SPEED   = 420.0     # 플레이어 이동 속도(픽셀/초)
PLAYER_PADDING = 32        # 코트 가장자리에서의 여유
RACKET_RADIUS  = 30        # 라켓/히트 박스 반경
HIT_COOLDOWN   = 0.25      # 한번 친 후 다음 타격까지 최소 간격(초)
BASE_HIT_SPEED = 420.0     # 기본 타구 속도
POWER_HIT_BONUS = 180.0    # 파워 스윙 보너스 속도(Space)

MIN_VY_AFTER_HIT = 320.0   # 타격 후 최소 수직 속도(상대편으로 확실히 넘어가도록)
CROSS_NUDGE_PX   = 14.0    # 타격 후 새 속도 방향으로 살짝 밀어내는 거리(겹침 방지)
COURT_OUTER_LINE_W = 6  # 바깥 라인 두께(draw의 MAIN_LINE_W와 같게 유지)

# 점수 애니메이션
SCORE_FLASH_DURATION = 0.45   # 깜빡임 총 시간(초)
SCORE_MAX_SCALE      = 1.25   # 글자 최대 확대 배율
SCORE_FLASH_COLOR    = (30, 144, 255)  # 하이라이트 색

# === 키 매핑 ===
KEY_SERVE = pygame.K_RETURN   # Enter로 서브
KEY_SMASH = pygame.K_SPACE    # Space는 스매시 전용

DIFFICULTY = {
    "easy":   {"speed_scale": 0.6, "aim_error": 50, "predict": 0.10, "swing_prob": 0.55},
    "normal": {"speed_scale": 0.9, "aim_error": 20, "predict": 0.40, "swing_prob": 0.85},
    "hard":   {"speed_scale": 1.2, "aim_error":  5, "predict": 0.80, "swing_prob": 1.00},
}

# =========================================================
# 2. UI 위젯 클래스 (버튼, 라벨 등)
# =========================================================
class Button:
    def __init__(self, text, center, size=(240, 64), bg=PRIMARY, fg=WHITE):
        self.text = text
        self.bg = bg
        self.fg = fg
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.hovered = False
        self.text_surf = FONT_M.render(text, True, self.fg)
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

    def draw(self, surf):
        color = tuple(min(255, c+25) for c in self.bg) if self.hovered else self.bg
        pygame.draw.rect(surf, color, self.rect, border_radius=12)
        pygame.draw.rect(surf, (0,0,0), self.rect, width=2, border_radius=12)
        surf.blit(self.text_surf, self.text_rect)

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def handle_event(self, event, on_click):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.hovered:
            on_click()

class Label:
    def __init__(self, text, center, font=FONT_L, color=BLACK):
        self.font = font
        self.color = color
        self.set_text(text)
        self.center = center

    def set_text(self, text):
        self.text = text
        self.surf = self.font.render(self.text, True, self.color)
        self.rect = self.surf.get_rect()

    def draw(self, surf):
        self.rect.center = self.center
        surf.blit(self.surf, self.rect)

# =========================================================
# 3. 씬(Scene) 기본 구조
# =========================================================
class Scene:
    def update(self, dt): ...
    def draw(self, surf): ...
    def handle_event(self, event): ...

class Player:
    def __init__(self, side, court_rect, is_human=False):
        self.side = side                  # "top" or "bottom"
        self.is_human = is_human
        self.court_rect = court_rect
        # 초기 위치: 자기 하프 중앙
        y = court_rect.top + court_rect.height * 0.20 if side == "top" else court_rect.bottom - court_rect.height * 0.20
        self.pos = [court_rect.centerx, y]
        self.swing_pressed = False
        self.last_hit_time = -999.0

    def allowed_rect(self):
        # 각 플레이어는 자기 하프에서만 이동
        half = self.court_rect.copy()
        if self.side == "top":
            half.height //= 2
        else:
            half.height //= 2
            half.top = self.court_rect.centery
        # 패딩 적용
        return half.inflate(-PLAYER_PADDING*2, -PLAYER_PADDING*2)

    def update_human(self, dt):
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_LEFT]:  dx -= PLAYER_SPEED * dt
        if keys[pygame.K_RIGHT]: dx += PLAYER_SPEED * dt
        if keys[pygame.K_UP]:    dy -= PLAYER_SPEED * dt
        if keys[pygame.K_DOWN]:  dy += PLAYER_SPEED * dt
        self.pos[0] += dx
        self.pos[1] += dy
        # 경계 클램프
        rect = self.allowed_rect()
        self.pos[0] = max(rect.left, min(rect.right, self.pos[0]))
        self.pos[1] = max(rect.top,  min(rect.bottom, self.pos[1]))

    def update_ai(self, dt, shuttle, diff=None):
        # 목표 x: 현재 x (가중) + 예측 x (가중)
        # 예측 시간: 셔틀이 내 y까지 도달하는 대략 시간
        vy = shuttle.vel[1]
        dy = abs(self.pos[1] - shuttle.pos[1])
        t_to_me = dy / max(60.0, abs(vy))   # 60은 안전 최소치로 폭주 방지

        predicted_x = shuttle.pos[0] + shuttle.vel[0] * t_to_me
        predict_w   = max(0.0, min(1.0, diff["predict"]))

        target_x = (1.0 - predict_w) * shuttle.pos[0] + predict_w * predicted_x
        # 에임 오차
        target_x += random.uniform(-diff["aim_error"], diff["aim_error"])

        # 이동 속도
        ai_speed = PLAYER_SPEED * diff["speed_scale"]
        if abs(target_x - self.pos[0]) > 2:
            step = ai_speed * dt
            if target_x > self.pos[0]:
                self.pos[0] += min(step, target_x - self.pos[0])
            else:
                self.pos[0] -= min(step, self.pos[0] - target_x)

        # 범위 클램프
        rect = self.allowed_rect()
        self.pos[0] = max(rect.left, min(rect.right, self.pos[0]))
        self.pos[1] = max(rect.top,  min(rect.bottom, self.pos[1]))

        # 스윙 확률: 셔틀이 근처일 때만 시도
        close_x = abs(shuttle.pos[0] - self.pos[0]) <= (RACKET_RADIUS + 20)
        close_y = abs(shuttle.pos[1] - self.pos[1]) <= 120
        self.swing_pressed = (close_x and close_y and (random.random() < diff["swing_prob"]))


    def update(self, dt, shuttle, diff=None):
        if self.is_human:
            self.update_human(dt)
        else:
            self.update_ai(dt, shuttle, diff if diff else DIFFICULTY["normal"])

    def can_hit(self, now, shuttle):
        # 쿨다운 + 같은 하프에 있을 때 + 셔틀 가까이
        if now - self.last_hit_time < HIT_COOLDOWN:
            return False
        if (self.side == "top" and shuttle.pos[1] >= self.court_rect.centery) or \
           (self.side == "bottom" and shuttle.pos[1] <  self.court_rect.centery):
            return False
        # 거리 체크(라켓 반경 + 셔틀 반경)
        import math
        dx = shuttle.pos[0] - self.pos[0]
        dy = shuttle.pos[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        return dist <= (RACKET_RADIUS + shuttle.radius + 4)

    def draw(self, surf):
        # 몸통(원), 라켓(원)
        color = (60, 60, 60) if self.is_human else (100, 100, 100)
        pygame.draw.circle(surf, color, (int(self.pos[0]), int(self.pos[1])), 16)
        # 라켓 표시
        pygame.draw.circle(surf, (0,0,0), (int(self.pos[0]), int(self.pos[1])), RACKET_RADIUS, width=2)

class Shuttle:
    def __init__(self, court_rect):
        self.court_rect = court_rect
        self.radius = 10
        self.pos = [court_rect.centerx, court_rect.centery]
        self.vel = [0.0, 0.0]

    def clamp_speed(self):
        import math
        speed = math.hypot(self.vel[0], self.vel[1])
        if speed > MAX_SPEED_SHUTTLE:
            k = MAX_SPEED_SHUTTLE / (speed + 1e-6)
            self.vel[0] *= k
            self.vel[1] *= k

    def update(self, dt):
        # 공기 저항
        self.vel[0] *= FRICTION_SHUTTLE
        self.vel[1] *= FRICTION_SHUTTLE
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.clamp_speed()

    def draw(self, surf):
        pygame.draw.circle(surf, PRIMARY, (int(self.pos[0]), int(self.pos[1])), self.radius)

# =========================================================
# 4. 메뉴 씬 (MenuScene)
# =========================================================

class MenuScene(Scene):
    def __init__(self, go_to_game, go_to_howto):
        self.title = Label("TEAM BJC - Badminton Junkies Crew", center=(WIDTH//2, 120))
        self.start_btn = Button("게임 시작", center=(WIDTH//2, 300))
        self.howto_btn = Button("조작법", center=(WIDTH//2, 380))
        self.quit_btn  = Button("종료", center=(WIDTH//2, 460))
        self.go_to_game = go_to_game
        self.go_to_howto = go_to_howto

    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self.start_btn.update(mouse_pos)
        self.howto_btn.update(mouse_pos)
        self.quit_btn.update(mouse_pos)

    def draw(self, surf):
        surf.fill(WHITE)
        self.title.draw(surf)
        self.start_btn.draw(surf)
        self.howto_btn.draw(surf)
        self.quit_btn.draw(surf)

        guide = [
            "조작: ←/→/↑/↓ 이동, Enter=서브, Space 스매시, R 랠리리셋, ESC 메뉴",
            f"목표 점수: {TARGET_SCORE} / 2점 차 규칙: {'ON' if TWO_POINT_RULE else 'OFF'} / 라운드 제한: {'무제한' if not ENABLE_TIME_LIMIT or ROUND_TIME<=0 else str(ROUND_TIME)+'초'}",
        ]
        for i, line in enumerate(guide):
            gsurf = FONT_S.render(line, True, (70,70,70))
            surf.blit(gsurf, (20, HEIGHT-90 + i*22))

        # 하단 크레딧
        credit = FONT_M.render("© BJC - Badminton Junkies Crew", True, (80,80,80))
        surf.blit(credit, (20, HEIGHT-40))

    def handle_event(self, event):
        self.start_btn.handle_event(event, self.go_to_game)
        self.howto_btn.handle_event(event, self.go_to_howto)
        self.quit_btn.handle_event(event, lambda: sys.exit(0))

class HowToScene(Scene):
    """조작법/규칙 안내 씬"""
    def __init__(self, go_back_menu):
        self.go_back_menu = go_back_menu
        self.title = Label("조작법 안내", center=(WIDTH//2, 90))
        self.back_btn = Button("뒤로", center=(WIDTH//2, HEIGHT-80), size=(160, 56))

        # 안내 텍스트 (원하는 대로 수정 가능)
        self.lines = [
            "방향키 ←/→/↑/↓ : 좌/우/앞/뒤 플레이어 이동",
            "Enter         : 서브 시작",
            "Space         : 스매시 (리시브의 1.5~2배 속도)",
            "",
            "서브 규칙:",
            "- 득점자가 다음 서브를 함",
            "- 자신의 점수 홀수 = 왼쪽, 짝수 = 오른쪽에서 서브",
            "- 서브는 자기 코트에서 대각 서비스 박스로"
        ]
        # 미리 렌더
        self.text_surfs = [FONT_S.render(t, True, (40,40,40)) for t in self.lines]

    def update(self, dt):
        self.back_btn.update(pygame.mouse.get_pos())

    def draw(self, surf):
        surf.fill((248, 250, 253))
        self.title.draw(surf)

        # 텍스트 블록 표시
        x = WIDTH//2 - 280
        y = 160
        box_w = 560
        line_h = 34

        # 배경 상자
        box_rect = pygame.Rect(x-20, y-20, box_w+40, line_h*len(self.text_surfs)+40)
        pygame.draw.rect(surf, (235,240,248), box_rect, border_radius=16)
        pygame.draw.rect(surf, (0,0,0), box_rect, width=2, border_radius=16)

        for i, ts in enumerate(self.text_surfs):
            surf.blit(ts, (x, y + i*line_h))

        self.back_btn.draw(surf)

    def handle_event(self, event):
        self.back_btn.handle_event(event, self.go_back_menu)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.go_back_menu()


# =========================================================
# 5. 게임 씬 (GameScene)
# =========================================================

class GameScene(Scene):
    def __init__(self, go_to_menu, go_to_gameover):
        self.go_to_menu = go_to_menu
        self.go_to_gameover = go_to_gameover
        self.info = Label("", center=(WIDTH//2, 40), font=FONT_M)
        self.last_hitter = None  # 마지막으로 친 쪽("top"/"bottom"), 연속 타격 방지/제어 용
        self.ai_serve_timer = 0.0

        # 셔틀 상태(데모)
        self.shuttle_pos = [WIDTH//2, HEIGHT//2]
        self.vel = [200, 120]
        self.radius = 10

        # --- 사운드 로드 ---
        def _load_sound(candidates):
            for path in candidates:
                try:
                    return pygame.mixer.Sound(path)
                except Exception:
                    pass
            return None  # 실패 시 None

        # 업로드된 파일(/mnt/data) 우선, 같은 폴더 파일명 후순위
        self.snd_receive = pygame.mixer.Sound("C:/Users/basra/OneDrive/바탕 화면/Gist/BJC/Python Program/badminton-83559.mp3")
        self.snd_smash = pygame.mixer.Sound("C:/Users/basra/OneDrive/바탕 화면/Gist/BJC/Python Program/table-smash-47690.mp3")
        self.snd_fail = pygame.mixer.Sound("C:/Users/basra/OneDrive/바탕 화면/Gist/BJC/Python Program/cartoon-fail-trumpet-278822.mp3")
        self.snd_win = pygame.mixer.Sound("C:/Users/basra/OneDrive/바탕 화면/Gist/BJC/Python Program/you-win-sequence-1-183948.mp3")

        # 볼륨 (원하면 수치 조정)
        if self.snd_receive: self.snd_receive.set_volume(0.75)
        if self.snd_smash:   self.snd_smash.set_volume(0.85)
        if self.snd_fail:    self.snd_fail.set_volume(0.85)
        if self.snd_win:     self.snd_win.set_volume(0.90)

        # ===== 코트 기하 =====
        self.COURT_H = 780
        self.COURT_W = int(self.COURT_H / 1.5)
        self.court_x = (WIDTH  - self.COURT_W) // 2
        self.court_y = (HEIGHT - self.COURT_H) // 2
        self.court_rect = pygame.Rect(self.court_x, self.court_y, self.COURT_W, self.COURT_H)
        self.cy = self.court_rect.centery            # 가로 중앙(= 네트)
        self.center_x = self.court_rect.centerx

        # 오브젝트
        self.shuttle = Shuttle(self.court_rect)
        self.player_bottom = Player("bottom", self.court_rect, is_human=True)
        self.player_top    = Player("top",    self.court_rect, is_human=False)

        # ===== 경기 상태 =====
        self.score = {"top": 0, "bottom": 0}
        self.server = "bottom"      # 시작 서브: bottom(플레이어측)
        self.rally_active = False   # 서브 대기/진행 여부
        self.round_time_left = float(ROUND_TIME) if (ENABLE_TIME_LIMIT and ROUND_TIME>0) else None
        self.time_elapsed = 0.0

        self.score_flash_t  = 0.0      # 남은 깜빡이 시간
        self.last_scored    = None     # 'top' or 'bottom' (누가 득점했는지)

        # ==== 난이도 ====
        self.diff_mode = "normal"          # "easy" / "normal" / "hard"
        self.diff      = DIFFICULTY[self.diff_mode]
        self.info.set_text(f"난이도: {self.diff_mode.upper()}  |  Space 서브")

        self.reset_serve(keep_server=True)

    # --- 사운드 헬퍼 ---
    def play_receive(self):
        if getattr(self, "snd_receive", None): self.snd_receive.play()

    def play_smash(self):
        if getattr(self, "snd_smash", None): self.snd_smash.play()

    def play_fail(self):
        if getattr(self, "snd_fail", None): self.snd_fail.play()

    def play_win(self):
        if getattr(self, "snd_win", None): self.snd_win.play()

    
    # --- 코트 하프(Rect) 도우미 ---
    def half_rect_for(self, side: str) -> pygame.Rect:
        r = self.court_rect.copy()
        r.height //= 2
        if side == "bottom":
            r.top = self.cy
        # side == "top"이면 위 하프 그대로
        return r

    # --- 서비스 지점 계산 ---
    # rule: 자신의 점수가 짝수면 '오른쪽', 홀수면 '왼쪽' (서버 '본인 기준'의 좌/우)
    # top은 화면 아래를 바라보므로 '본인 기준 오른쪽' == 화면 왼쪽, bottom은 화면 위를 바라봐서 오른쪽==화면 오른쪽.
    def serve_spot(self, side: str) -> tuple[int, int]:
        even = (self.score[side] % 2 == 0)
        which = "right" if even else "left"
        return self.side_spot(side, which)

    
        # --- 한쪽 면의 '오른쪽/왼쪽' 서비스 지점 (그 쪽 선수의 시점 기준) ---
    def side_spot(self, side: str, which: str) -> tuple[int, int]:
        """
        side: 'top' 또는 'bottom'
        which: 'right' 또는 'left'  (해당 side 선수의 '오른쪽/왼쪽' 개념)
        """
        half = self.half_rect_for(side)
        x_offset = int(half.width * 0.25)

        if side == "bottom":
            # bottom의 '오른쪽' = 화면 오른쪽
            x = half.centerx + (x_offset if which == "right" else -x_offset)
            y = int(half.bottom - half.height * 0.20)
        else:
            # top의 '오른쪽' = 화면 왼쪽 (시점 반대)
            x = half.centerx - (x_offset if which == "right" else -x_offset)
            y = int(half.top + half.height * 0.20)
        return x, y

    # --- (server 기준) 리시브 시작 지점: 대각 서비스 코트 ---
    def receive_spot(self, server_side: str) -> tuple[int, int]:
        """
        server_side의 현재 점수 짝/홀을 기준으로,
        상대는 '대각선' 서비스 코트에서 시작.
        => server가 오른쪽에서 서브면, 상대도 자신의 '오른쪽' 서비스 박스에서 대기
        """
        opponent = "top" if server_side == "bottom" else "bottom"
        even = (self.score[server_side] % 2 == 0)
        which = "right" if even else "left"
        return self.side_spot(opponent, which)


    # ------------ 유틸 ------------
    def place_for_serve(self):
        # 서버/리시버 시작 위치 계산
        sx, sy = self.serve_spot(self.server)              # 서버 위치
        rx, ry = self.receive_spot(self.server)            # 리시버(대각) 위치

        server_player   = self.player_bottom if self.server == "bottom" else self.player_top
        receiver_player = self.player_top    if self.server == "bottom" else self.player_bottom

        # 플레이어들을 해당 위치로 배치
        server_player.pos[0], server_player.pos[1]   = sx, sy
        receiver_player.pos[0], receiver_player.pos[1] = rx, ry

        # 셔틀은 서버 바로 '앞'에 배치 (겹침 방지 위해 약간 오프셋)
        if self.server == "bottom":
            self.shuttle.pos = [sx, sy - 36]  # 아래쪽 서버는 위쪽으로 36px
        else:
            self.shuttle.pos = [sx, sy + 36]  # 위쪽 서버는 아래쪽으로 36px
        self.shuttle.vel = [0.0, 0.0]


    def reset_serve(self, keep_server=False):
        self.rally_active = False
        self.place_for_serve()
        if ENABLE_TIME_LIMIT and ROUND_TIME>0:
            self.round_time_left = float(ROUND_TIME)

        # 🟢 추가: 랠리 시작 전 상태 초기화
        self.last_hitter = None
        self.player_bottom.swing_pressed = False
        self.player_top.swing_pressed = False
        self.player_bottom.last_hit_time = -999.0
        self.player_top.last_hit_time = -999.0

        # 안내 + AI 자동 서브 타이머
        if self.server == "bottom":
            self.info.set_text("서브 대기: BOTTOM – Enter로 시작")
            self.ai_serve_timer = 0.0
        else:
            self.info.set_text("서브 대기: TOP – AI가 곧 서브")
            self.ai_serve_timer = 0.6   # AI가 서버면 0.6초 후 자동 서브

    def start_rally(self):
        self.rally_active = True
        speed = BASE_HIT_SPEED + 80
        # 서버가 위/아래에 따라 초기 방향
        self.shuttle.vel = [0.0, -speed] if self.server == "bottom" else [0.0, speed]
        self.info.set_text("랠리 진행 중")

        # 🟢 추가: 서버가 첫 타자
        self.last_hitter = self.server

    def side_of_y(self, y):
        return "top" if y < self.cy else "bottom"

    def award_point(self, winner, reason):
        self.score[winner] += 1
        # 플레이어(bottom) 기준 승/패 사운드
        if winner == "bottom":
            self.play_win()
        else:
            self.play_fail()
        # --- 점수 애니메이션 시작 ---
        self.last_scored   = winner
        self.score_flash_t = SCORE_FLASH_DURATION
        self.server = winner
        if self.is_game_over():
            w = "TOP" if self.score["top"] > self.score["bottom"] else "BOTTOM"
            self.go_to_gameover({"top": self.score["top"], "bottom": self.score["bottom"]}, reason, w)
            return
        
        # 다음 서브로 전환
        self.reset_serve(keep_server=True)

    def is_game_over(self):
        t = self.score["top"]; b = self.score["bottom"]
        lead = abs(t - b)
        mx = max(t, b)
        if TWO_POINT_RULE:
            # 일반 규정(최대 30점 cap은 생략): 목표점 이상 + 2점차
            return (mx >= TARGET_SCORE) and (lead >= 2)
        else:
            # 목표점 먼저 도달
            return mx >= TARGET_SCORE
        
    # ------------ 충돌/타격 ------------
    def try_hit(self, player, now):

        # 같은 편이 연속으로 치는 것 잠깐 금지(셔틀이 아직 자기 하프에 있으면)
        if self.last_hitter == player.side and self.side_of_y(self.shuttle.pos[1]) == player.side:
            return

        # 기본 충돌 가능 체크(쿨다운/반경/하프)
        if not player.can_hit(now, self.shuttle):
            return

        # === 리시브/스매시 판단 ===
        # 사람: 스페이스 누르면 스매시, 아니면 자동 리시브
        # AI: update_ai에서 swing_pressed 결정(스매시 확률/상황), 아니면 자동 리시브
        is_smash = player.swing_pressed

        # 목표 x: 상대 위치를 살짝 겨냥(너무 정확하지 않게 살짝만 보정)
        opponent = self.player_top if player.side == "bottom" else self.player_bottom
        target_x = opponent.pos[0]
        nx = max(-1.0, min(1.0, (target_x - self.shuttle.pos[0]) / 120.0))

        # 파워
        power = BASE_HIT_SPEED + (POWER_HIT_BONUS if is_smash else 0.0)

        # 반대 코트로 보냄
        vy_sign = -1.0 if player.side == "bottom" else 1.0
        vx = power * 0.6 * nx
        vy = power * vy_sign

        # 최소 수직 속도 보장(네트 넘어가게)
        try:
            MIN_VY = MIN_VY_AFTER_HIT
        except NameError:
            MIN_VY = 320.0  # 상수 안 쓰셨다면 기본값
        if abs(vy) < MIN_VY:
            vy = MIN_VY * vy_sign

        # 속도 적용
        self.shuttle.vel = [vx, vy]

        # 약간 앞으로 밀어 겹침/재히트 방지
        import math
        speed = math.hypot(vx, vy)
        try:
            NUDGE = CROSS_NUDGE_PX
        except NameError:
            NUDGE = 14.0
        if speed > 1e-6:
            self.shuttle.pos[0] += (vx / speed) * NUDGE
            self.shuttle.pos[1] += (vy / speed) * NUDGE

        # 상태 갱신
        player.last_hit_time = now
        self.last_hitter = player.side

        # 타구 사운드
        if is_smash:
            self.play_smash()
        else:
            self.play_receive()


    def update(self, dt):
        now = pygame.time.get_ticks() / 1000.0
        self.time_elapsed += dt

        keys = pygame.key.get_pressed()

        # ─ 서브 대기 상태 ─
        if not self.rally_active:
            # AI가 서버면 자동 서브 타이머
            if self.server == "top":
                if self.ai_serve_timer > 0:
                    self.ai_serve_timer -= dt
                    if self.ai_serve_timer <= 0:
                        self.start_rally()
            return
        
        # 리시브: 셔틀콕이 플레이어 근처에 오면 자동 리시브
        if self.rally_active:
            # 플레이어와 셔틀 간 거리 계산 (리시브 범위: RACKET_RADIUS + 20px)
            distance_to_shuttle = abs(self.shuttle.pos[0] - self.player_bottom.pos[0]) + abs(self.shuttle.pos[1] - self.player_bottom.pos[1])
            
            # 리시브 범위 내에 있으면 자동 리시브
            if distance_to_shuttle < RACKET_RADIUS + 20:
                self.shuttle.vel[0] *= 1  # 속도 유지 (리시브 후 속도 변경 없음)
                self.shuttle.vel[1] *= 1  # 속도 유지 (리시브 후 속도 변경 없음)
                # 리시브 후 랠리는 계속 진행
                self.rally_active = True

        # 스매시: 스페이스 키 눌렀을 때
        if self.rally_active:
            if keys[pygame.K_SPACE]:  # 스페이스 키로 스매시
                self.shuttle.vel[0] *= 2  # x축 속도 두 배
                self.shuttle.vel[1] *= 2  # y축 속도 두 배
                self.rally_active = True  # 스매시 후에도 랠리 계속

        # 셔틀 이동
        self.shuttle.update(dt)

        # 플레이어 입력/AI
        self.player_bottom.swing_pressed = keys[pygame.K_SPACE]

        self.player_bottom.update(dt, self.shuttle, self.diff)
        self.player_top.update(dt, self.shuttle, self.diff)

        # 라켓 타격 판정(먼저 상대 쪽, 동시에 두 번 치는 걸 줄이기 위해 순서)
        if self.side_of_y(self.shuttle.pos[1]) == "bottom":
            self.try_hit(self.player_bottom, now)
            self.try_hit(self.player_top, now)
        else:
            self.try_hit(self.player_top, now)
            self.try_hit(self.player_bottom, now)

        # ---- 간단판 OUT/LINE 판정 ----
        # 규칙:
        # - 좌/우 사이드: 선에 닿거나(라인 밴드) 밖으로 나가면 → 마지막 타자의 '상대' 득점
        # - 위/아래 베이스: '밖으로 넘어가면'만 → 못 친 쪽(= 마지막 타자의 상대) 패 → 마지막 타자 득점
        r = self.shuttle.radius
        cx, cy = self.shuttle.pos
        outer = self.court_rect
        line_w = COURT_OUTER_LINE_W if 'COURT_OUTER_LINE_W' in globals() else 6

        # 1) 바깥으로 '넘어감'
        if cx < outer.left or cx > outer.right or cy < outer.top or cy > outer.bottom:
            # 1-a) 좌/우로 나감 → 사이드 아웃: 마지막 타자의 '상대' 득점
            if cx < outer.left or cx > outer.right:
                hitter = self.last_hitter or self.server
                winner = "top" if hitter == "bottom" else "bottom"
                self.award_point(winner, "Side out")
                return
            # 1-b) 위/아래로 나감 → 베이스 아웃: 마지막 타자 득점(= 수신측 패)
            hitter = self.last_hitter or self.server
            self.award_point(hitter, "Baseline out")
            return

        # 2) 코트 안이지만 '사이드 라인 밴드'에 닿음 (베이스 라인 접촉은 인으로 취급)
        on_left_side_line  = (outer.left <= cx <= outer.left + line_w)
        on_right_side_line = (outer.right - line_w <= cx <= outer.right)
        if on_left_side_line or on_right_side_line:
            hitter = self.last_hitter or self.server
            winner = "top" if hitter == "bottom" else "bottom"
            self.award_point(winner, "Side line")
            return
        # 점수 깜빡이 타이머 감소
        if self.score_flash_t > 0:
            self.score_flash_t = max(0.0, self.score_flash_t - dt)



    def draw(self, surf):
        surf.fill((245, 250, 255))
        self.info.draw(surf)

        # ===== 스타일 =====
        MAIN_LINE_COLOR = (0, 0, 0)  # 바깥 코트 테두리 & 가로 중앙선(네트)
        MAIN_LINE_W     = 6
        SUB_LINE_COLOR  = (128, 128, 128)
        SUB_LINE_W      = 3

        court_rect = self.court_rect
        cy = self.cy
        center_x = self.center_x

        # 바깥 코트 테두리
        pygame.draw.rect(surf, MAIN_LINE_COLOR, court_rect, width=MAIN_LINE_W, border_radius=18)

        # 중앙선(네트)
        pygame.draw.line(surf, MAIN_LINE_COLOR, (court_rect.left, cy), (court_rect.right, cy), width=MAIN_LINE_W)

        # 위/아래 보조선 두 개(시각적 가이드)
        top_y = court_rect.top
        bottom_y = court_rect.bottom
        x_top = cy - top_y
        x_bottom = bottom_y - cy

        y_up_from_center = int(cy - x_top / 4)
        y_down_from_top  = int(top_y + x_top / 4)
        y_down_from_center = int(cy + x_bottom / 4)
        y_up_from_bottom   = int(bottom_y - x_bottom / 4)

        for y in [y_up_from_center, y_down_from_top, y_down_from_center, y_up_from_bottom]:
            pygame.draw.line(surf, SUB_LINE_COLOR, (court_rect.left, y), (court_rect.right, y), width=SUB_LINE_W)

        # 세로 중앙선
        pygame.draw.line(surf, SUB_LINE_COLOR, (center_x, court_rect.top), (center_x, court_rect.bottom), width=SUB_LINE_W)

        # 오브젝트
        self.player_top.draw(surf)
        self.player_bottom.draw(surf)
        self.shuttle.draw(surf)

        # 스코어/상태 보드
        BOARD_W, BOARD_H = 120, 60
        margin_court = 10

        x_left = court_rect.right + margin_court
        y_top  = court_rect.centery - BOARD_H // 2
        board_rect = pygame.Rect(x_left, y_top, BOARD_W, BOARD_H)

        pygame.draw.rect(surf, (255, 255, 255), board_rect, border_radius=12)
        pygame.draw.rect(surf, (0, 0, 0), board_rect, width=2, border_radius=12)

        # --- 애니메이션용 색/스케일 계산 ---
        # t=0~1로 정규화, 앞/뒤로 부드럽게 펄스(색+스케일)
        if self.score_flash_t > 0:
            t = 1.0 - (self.score_flash_t / SCORE_FLASH_DURATION)  # 진행도 0→1
            # ease-out-in 느낌
            import math
            ease = 0.5 - 0.5 * math.cos(math.pi * t)  # 0→1 부드럽게

            # 색 보간: BLACK -> SCORE_FLASH_COLOR -> BLACK
            def lerp(a,b,u): return int(a + (b-a)*u)
            # 왕복 느낌: 앞 절반 up, 뒤 절반 down
            updown = (ease if ease <= 0.5 else 1.0 - (ease-0.5)*2)
            u = updown * 2.0 if ease <= 0.5 else (1.0 - updown) * 2.0
            u = max(0.0, min(1.0, u))

            col = tuple(lerp(0, c, u) for c in SCORE_FLASH_COLOR)

            # 스케일: 1.0 -> SCORE_MAX_SCALE -> 1.0
            scale = 1.0 + (SCORE_MAX_SCALE - 1.0) * (1.0 - abs(1.0 - 2.0*ease))
        else:
            col = (0, 0, 0)
            scale = 1.0

        # 점수 문자열
        score_text = f"{self.score['top']} : {self.score['bottom']}"

        # 기본 렌더 후 스케일
        text_surface = FONT_M.render(score_text, True, col)
        if scale != 1.0:
            w, h = text_surface.get_size()
            text_surface = pg_transform.smoothscale(text_surface, (w, h))


        # 중앙 배치
        surf.blit(
            text_surface,
            (board_rect.centerx - text_surface.get_width() // 2,
            board_rect.centery - text_surface.get_height() // 2)
        )
        # 하단 도움말
        help1 = FONT_S.render("←/→/↑/↓: 속도조절  | Enter=서브 |  Space: 스매시  |  R: 랠리 리셋  |  ESC: 메뉴", True, (80,80,80))
        surf.blit(help1, (WIDTH//2 - help1.get_width()//2, HEIGHT - 36))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_to_menu()
            elif event.key == pygame.K_r:
                self.reset_serve(keep_server=True)
            elif (event.key == KEY_SERVE) and (not self.rally_active) and (self.server == "bottom"):
                self.start_rally()

# =========================================================
# 5.5 GameOverScene
# =========================================================
class GameOverScene(Scene):
    def __init__(self, score, reason, winner, go_to_menu, go_to_game):
        self.title = Label("GAME OVER", center=(WIDTH//2, 120))
        detail = f"Reason: {reason} | Winner: {winner} | TOP {score['top']} : {score['bottom']} BOTTOM"
        self.detail = Label(detail, center=(WIDTH//2, 180), font=FONT_M)
        self.menu_btn = Button("메뉴로", center=(WIDTH//2 - 150, 320))
        self.retry_btn = Button("다시하기", center=(WIDTH//2 + 150, 320))
        self.go_to_menu = go_to_menu
        self.go_to_game = go_to_game

    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self.menu_btn.update(mouse_pos)
        self.retry_btn.update(mouse_pos)

    def draw(self, surf):
        surf.fill(WHITE)
        self.title.draw(surf)
        self.detail.draw(surf)
        self.menu_btn.draw(surf)
        self.retry_btn.draw(surf)

    def handle_event(self, event):
        self.menu_btn.handle_event(event, self.go_to_menu)
        self.retry_btn.handle_event(event, self.go_to_game)

# =========================================================
# 6. 메인 실행 루프
# =========================================================
def main():
    # 씬 전환 콜백 정의
    current_scene = {"scene": None}
    def go_to_menu():
        current_scene["scene"] = MenuScene(go_to_game, go_to_howto)
    def go_to_game():
        current_scene["scene"] = GameScene(go_to_menu, go_to_gameover)

    def go_to_howto():
        current_scene["scene"] = HowToScene(go_to_menu)

    def go_to_gameover(score, reason, winner):
        current_scene["scene"] = GameOverScene(score, reason, winner, go_to_menu, go_to_game)


    go_to_menu()  # 시작은 메뉴

    while True:
        dt = clock.tick(FPS) / 1000.0  # 초 단위
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            current_scene["scene"].handle_event(event)

        current_scene["scene"].update(dt)
        current_scene["scene"].draw(screen)
        pygame.display.flip()

if __name__ == "__main__":
    main()
