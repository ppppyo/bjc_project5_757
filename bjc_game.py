import pygame
import sys
# =========================================================
# 1. 기본 설정 & 전역 상수
# =========================================================

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

    def update_ai(self, dt, shuttle):
        # 간단한 추적 AI: 셔틀 x로 보정, y는 하프 내 유지
        target_x = shuttle.pos[0]
        ax = 0.0
        if abs(target_x - self.pos[0]) > 4:
            ax = PLAYER_SPEED * (1 if target_x > self.pos[0] else -1)
        self.pos[0] += ax * dt * 0.75  # 반응 속도 낮춰서 자연스럽게
        rect = self.allowed_rect()
        self.pos[0] = max(rect.left, min(rect.right, self.pos[0]))
        self.pos[1] = max(rect.top,  min(rect.bottom, self.pos[1]))
        # 자동 스윙: 셔틀이 내 하프로 접근/체공 시 타격 시도
        self.swing_pressed = True

    def update(self, dt, shuttle):
        if self.is_human:
            self.update_human(dt)
        else:
            self.update_ai(dt, shuttle)

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
            "조작: ←/→/↑/↓ 속도 조절, Space 서브, R 랠리리셋, ESC 메뉴",
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
            "Enter         : 스매시 (리시브의 1.5~2배 속도)",
            "Space         : 리시브",
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

        self.reset_serve(keep_server=True)

    # ------------ 유틸 ------------
    def place_for_serve(self):
        # 서버 옆에서 살짝 뒤쪽 위치에 셔틀 배치
        if self.server == "bottom":
            self.shuttle.pos = [self.player_bottom.pos[0], self.player_bottom.pos[1] - 40]
        else:
            self.shuttle.pos = [self.player_top.pos[0], self.player_top.pos[1] + 40]
        self.shuttle.vel = [0.0, 0.0]

    def reset_serve(self, keep_server=False):
        self.rally_active = False
        self.place_for_serve()
        if ENABLE_TIME_LIMIT and ROUND_TIME>0:
            self.round_time_left = float(ROUND_TIME)
        self.info.set_text(f"서브 대기: {self.server.upper()} - Space로 시작")

    def start_rally(self):
        self.rally_active = True
        speed = BASE_HIT_SPEED + 80
        # 서버가 위/아래에 따라 초기 방향
        self.shuttle.vel = [0.0, -speed] if self.server == "bottom" else [0.0, speed]
        self.info.set_text("랠리 진행 중")

    def side_of_y(self, y):
        return "top" if y < self.cy else "bottom"

    def award_point(self, winner, reason):
        self.score[winner] += 1
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
        # 사람: Space 눌렀을 때만 스윙, AI: 자동 스윙 플래그
        if player.is_human and not player.swing_pressed:
            return

        # 같은 편이 연속으로 치는 것 잠깐 금지(셔틀이 아직 자기 하프에 있으면)
        if self.last_hitter == player.side and self.side_of_y(self.shuttle.pos[1]) == player.side:
            return

        if not player.can_hit(now, self.shuttle):
            return

        import math

        # 상대편 기본 목표 x (상대 위치로 살짝 유도)
        opponent = self.player_top if player.side == "bottom" else self.player_bottom
        target_x = opponent.pos[0]

        # 스윙 파워
        power = BASE_HIT_SPEED + (POWER_HIT_BONUS if player.is_human and player.swing_pressed else 0.0)

        # x 방향은 상대의 x 쪽으로 제한된 비율로 유도
        nx = max(-1.0, min(1.0, (target_x - self.shuttle.pos[0]) / 120.0))
        vx = power * 0.6 * nx

        # y 방향은 반드시 '상대편'으로
        vy_sign = -1.0 if player.side == "bottom" else 1.0
        vy = power * vy_sign

        # 최소 수직 속도 보장(상대편으로 확실히 넘어가게)
        if abs(vy) < MIN_VY_AFTER_HIT:
            vy = MIN_VY_AFTER_HIT * vy_sign

        # 새 속도 적용
        self.shuttle.vel = [vx, vy]

        # 겹침/재히트 방지를 위해 새 속도 방향으로 살짝 밀어줌
        speed = math.hypot(vx, vy)
        if speed > 1e-6:
            self.shuttle.pos[0] += (vx / speed) * CROSS_NUDGE_PX
            self.shuttle.pos[1] += (vy / speed) * CROSS_NUDGE_PX

        # 상태 업데이트
        player.last_hit_time = now
        self.last_hitter = player.side

    def update(self, dt):
        now = pygame.time.get_ticks() / 1000.0
        self.time_elapsed += dt

        keys = pygame.key.get_pressed()

        # 서브 대기 중 Space 로 랠리 시작
        if not self.rally_active:
            if keys[pygame.K_SPACE]:
                self.start_rally()
            # 서브 대기 중에는 속도 조절 무시, 위치만 표시
            return

        # 남은 시간 처리
        if ENABLE_TIME_LIMIT and self.round_time_left is not None:
            self.round_time_left -= dt
            if self.round_time_left <= 0:
                # 시간 초과: 상대 득점
                loser = self.side_of(self.shuttle_pos[1])  # 셔틀이 있는 쪽이 실격
                winner = "bottom" if loser == "top" else "top"
                self.award_point(winner, "Time over")
                return
        # 플레이어 입력/AI
        self.player_bottom.swing_pressed = keys[pygame.K_SPACE]
        self.player_bottom.update(dt, self.shuttle)
        self.player_top.update(dt, self.shuttle)

        # 셔틀 이동
        self.shuttle.update(dt)

        # 라켓 타격 판정(먼저 상대 쪽, 동시에 두 번 치는 걸 줄이기 위해 순서)
        if self.side_of_y(self.shuttle.pos[1]) == "bottom":
            self.try_hit(self.player_bottom, now)
            self.try_hit(self.player_top, now)
        else:
            self.try_hit(self.player_top, now)
            self.try_hit(self.player_bottom, now)

        # 아웃 판정
        r = self.shuttle.radius
        if not self.court_rect.inflate(-r*2, -r*2).collidepoint(self.shuttle.pos[0], self.shuttle.pos[1]):
            loser_side = self.side_of_y(self.shuttle.pos[1])
            winner_side = "bottom" if loser_side == "top" else "top"
            self.award_point(winner_side, f"Out - {loser_side.upper()}")
            return

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
        board_rect = pygame.Rect(0, 0, WIDTH-40, 100)
        board_rect.center = (WIDTH//2, 80)
        pygame.draw.rect(surf, (255,255,255), board_rect, border_radius=12)
        pygame.draw.rect(surf, (0,0,0), board_rect, width=2, border_radius=12)

        score_text = f"TOP {self.score['top']}  :  {self.score['bottom']} BOTTOM"
        server_text = f"Server: {'BOTTOM' if self.server=='bottom' else 'TOP'}"
        time_text = ""
        if ENABLE_TIME_LIMIT and self.round_time_left is not None:
            time_text = f"Time: {max(0, int(self.round_time_left))}s"

        s1 = FONT_M.render(score_text, True, BLACK)
        s2 = FONT_S.render(server_text, True, (60,60,60))
        s3 = FONT_S.render(time_text, True, (60,60,60)) if time_text else None

        surf.blit(s1, (board_rect.centerx - s1.get_width()//2, board_rect.top + 8))
        surf.blit(s2, (board_rect.left + 16, board_rect.bottom - 30))
        if s3:
            surf.blit(s3, (board_rect.right - 16 - s3.get_width(), board_rect.bottom - 30))

        # 하단 도움말
        help1 = FONT_S.render("←/→/↑/↓: 속도조절  |  Space: 서브  |  R: 랠리 리셋  |  ESC: 메뉴", True, (80,80,80))
        surf.blit(help1, (WIDTH//2 - help1.get_width()//2, HEIGHT - 36))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_to_menu()
            elif event.key == pygame.K_r:
                self.reset_serve(keep_server=True)


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
