import pygame
import sys
import math
import random

DEBUG = False
def dbg(*a):
    if DEBUG:
        print("[DBG]", *a)

# ------------------------------------------------------------------------------
# Basic setup
# ------------------------------------------------------------------------------
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
pygame.init()

SCREEN_W, SCREEN_H = 800, 900
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("BJC - Badminton Junkies Crew")
clock = pygame.time.Clock()

# Colors / Fonts 
WHITE   = (255, 255, 255)
BLACK   = (0, 0, 0)
PRIMARY = (30, 144, 255)

FONT_L = pygame.font.SysFont("malgungothic", 45)
FONT_M = pygame.font.SysFont("malgungothic", 25)
FONT_S = pygame.font.SysFont("malgungothic", 18)

# ------------------------------------------------------------------------------
# Game rules & physics parameters
# ------------------------------------------------------------------------------
TARGET_SCORE       = 21
TWO_POINT_RULE     = False

PLAYER_SPEED   = 420.0
PLAYER_PADDING = 32
RACKET_RADIUS  = 30
HIT_COOLDOWN   = 0.25

BASE_HIT_SPEED   = 420.0
POWER_HIT_BONUS  = 180.0
MIN_VY_AFTER_HIT = 320.0
CROSS_NUDGE_PX   = 14.0

MAX_SPEED_SHUTTLE = 520.0
FRICTION_SHUTTLE  = 0.995

SCORE_FLASH_DUR = 0.45
SCORE_FLASH_COL = (30, 144, 255)

KEY_SERVE = pygame.K_RETURN

DIFFICULTY = {
    "easy":   {"speed_scale": 0.62, "aim_error": 48, "predict": 0.12, "swing_prob": 0.55},
    "normal": {"speed_scale": 0.9,  "aim_error": 22, "predict": 0.40, "swing_prob": 0.85},
    "hard":   {"speed_scale": 1.2,  "aim_error":  6, "predict": 0.80, "swing_prob": 1.00},
}

# ------------------------------------------------------------------------------
# UI widgets
# ------------------------------------------------------------------------------
class Button:
    def __init__(self, text, center, size=(240, 64), bg=PRIMARY, fg=WHITE):
        self.text = text
        self.bg = bg
        self.fg = fg
        self.rect = pygame.Rect(0, 0, *size); self.rect.center = center
        self.hovered = False
        self.text_surf = FONT_M.render(text, True, fg)
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def handle_event(self, evt, on_click):
        if evt.type == pygame.MOUSEBUTTONDOWN and evt.button == 1 and self.hovered:
            on_click()

    def draw(self, surf):
        c = tuple(min(255, ch + 25) for ch in self.bg) if self.hovered else self.bg
        pygame.draw.rect(surf, c, self.rect, border_radius=12)
        pygame.draw.rect(surf, BLACK, self.rect, width=2, border_radius=12)
        surf.blit(self.text_surf, self.text_rect)

class Label:
    def __init__(self, text, center, font=FONT_L, color=BLACK):
        self.font, self.color = font, color
        self.center = center
        self.set_text(text)

    def set_text(self, text):
        self.text = text
        self.surf = self.font.render(self.text, True, self.color)
        self.rect = self.surf.get_rect()
        self.rect.center = self.center

    def draw(self, surf):
        self.rect.center = self.center
        surf.blit(self.surf, self.rect)

# ------------------------------------------------------------------------------
# Scene base
# ------------------------------------------------------------------------------
class Scene:
    def update(self, dt): ...
    def draw(self, surf): ...
    def handle_event(self, evt): ...

# ------------------------------------------------------------------------------
# Player & Shuttle
# ------------------------------------------------------------------------------
class Player:
    def __init__(self, side, court_rect, is_human=False):
        self.side = side  # "top" / "bottom"
        self.is_human = is_human
        self.court_rect = court_rect
        y0 = court_rect.top + court_rect.height * 0.20 if side == "top" else court_rect.bottom - court_rect.height * 0.20
        self.pos = [court_rect.centerx, y0]
        self.swing_pressed = False
        self.last_hit_time = -999.0

    def _allowed_rect(self):
        half = self.court_rect.copy()
        half.height //= 2
        if self.side == "bottom":
            half.top = self.court_rect.centery
        return half.inflate(-PLAYER_PADDING*2, -PLAYER_PADDING*2)

    def update_human(self, dt):
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * PLAYER_SPEED * dt
        dy = (keys[pygame.K_DOWN]  - keys[pygame.K_UP])   * PLAYER_SPEED * dt
        self.pos[0] += dx; self.pos[1] += dy
        box = self._allowed_rect()
        self.pos[0] = max(box.left, min(box.right,  self.pos[0]))
        self.pos[1] = max(box.top,  min(box.bottom, self.pos[1]))

    def update_ai(self, dt, shuttle, diff):
        # ----------------------------------------------------------------------
        # AI Prediction (part of "Shuttlecock Trajectory Algorithm" feature)
        # Predict where the shuttle will be horizontally by the time it reaches
        # our half. We use a crude time-to-intercept from current vertical speed.
        # Add a bit of aim error so the AI doesn't feel robotic.
        # ----------------------------------------------------------------------
        vy = shuttle.vel[1]
        dy = abs(self.pos[1] - shuttle.pos[1])
        t_to_me = dy / max(60.0, abs(vy))  
        predicted_x = shuttle.pos[0] + shuttle.vel[0] * t_to_me

        w = max(0.0, min(1.0, diff["predict"]))
        target_x = (1 - w) * shuttle.pos[0] + w * predicted_x
        target_x += random.uniform(-diff["aim_error"], diff["aim_error"])

        v = PLAYER_SPEED * diff["speed_scale"]
        step = v * dt
        if abs(target_x - self.pos[0]) > 2:
            self.pos[0] += step if target_x > self.pos[0] else -step

        box = self._allowed_rect()
        self.pos[0] = max(box.left, min(box.right,  self.pos[0]))
        self.pos[1] = max(box.top,  min(box.bottom, self.pos[1]))

        near_x = abs(shuttle.pos[0] - self.pos[0]) <= (RACKET_RADIUS + 18)
        near_y = abs(shuttle.pos[1] - self.pos[1]) <= 120
        self.swing_pressed = (near_x and near_y and (random.random() < diff["swing_prob"]))

    def update(self, dt, shuttle, diff=None):
        if self.is_human:
            self.update_human(dt)
        else:
            self.update_ai(dt, shuttle, diff or DIFFICULTY["normal"])

    def can_hit(self, now, shuttle):
        # Disallow spamming hits: use cooldown and half-court checks.
        if now - self.last_hit_time < HIT_COOLDOWN:
            return False
        # Can't hit if shuttle is not in our half.
        if (self.side == "top" and shuttle.pos[1] >= self.court_rect.centery) or \
           (self.side == "bottom" and shuttle.pos[1] <  self.court_rect.centery):
            return False
        dx = shuttle.pos[0] - self.pos[0]
        dy = shuttle.pos[1] - self.pos[1]
        return math.hypot(dx, dy) <= (RACKET_RADIUS + shuttle.radius + 4)

    def draw(self, surf):
        pygame.draw.circle(surf, (70,70,70) if self.is_human else (110,110,110),
                           (int(self.pos[0]), int(self.pos[1])), 16)
        pygame.draw.circle(surf, BLACK, (int(self.pos[0]), int(self.pos[1])), RACKET_RADIUS, 2)

class Shuttle:
    def __init__(self, court_rect):
        self.court_rect = court_rect
        self.radius = 10
        self.pos = [court_rect.centerx, court_rect.centery]
        self.vel = [0.0, 0.0]

    def update(self, dt):
        # ----------------------------------------------------------------------
        # Shuttlecock Trajectory Algorithm (core update)
        # 1) Air drag: gradually dampen velocity to simulate air resistance.
        # 2) Integrate position from velocity (classic Euler step).
        # 3) Clamp peak speed to avoid unrealistic movement bursts.
        # NOTE: We don't add gravity; badminton shuttle "floats" due to drag,
        # and we keep it arcade-like. If you want gravity, add vel[1] += g*dt.
        # ----------------------------------------------------------------------
        self.vel[0] *= FRICTION_SHUTTLE
        self.vel[1] *= FRICTION_SHUTTLE
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

        sp = math.hypot(self.vel[0], self.vel[1])
        if sp > MAX_SPEED_SHUTTLE:
            k = MAX_SPEED_SHUTTLE / (sp + 1e-6)
            self.vel[0] *= k; self.vel[1] *= k

    def draw(self, surf):
        # ----------------------------------------------------------------------
        # Dynamic Visuals: crisp, simple shuttle representation
        # (You can replace this with an image or a gradient for more flair.)
        # ----------------------------------------------------------------------
        pygame.draw.circle(surf, PRIMARY, (int(self.pos[0]), int(self.pos[1])), self.radius)

# ------------------------------------------------------------------------------
# Menu / Help Scenes
# ------------------------------------------------------------------------------
class MenuScene(Scene):
    def __init__(self, go_game, go_howto, quit_game):
        self.title = Label("TEAM BJC - Badminton Junkies Crew", (SCREEN_W//2, 120))
        self.start_btn = Button("Game Start", (SCREEN_W//2, 300))
        self.howto_btn = Button("How to Operate", (SCREEN_W//2, 380))
        self.quit_btn  = Button("Game Over", (SCREEN_W//2, 460))
        self.go_game, self.go_howto, self.quit_game = go_game, go_howto, quit_game

    def update(self, dt):
        m = pygame.mouse.get_pos()
        self.start_btn.update(m); self.howto_btn.update(m); self.quit_btn.update(m)

    def draw(self, surf):
        surf.fill(WHITE)
        self.title.draw(surf)
        for b in (self.start_btn, self.howto_btn, self.quit_btn): b.draw(surf)

        lines = [
            "←/→/↑/↓ : Move, Enter = Serve, Space = Smash, ESC = Menu",
            f"Target Score : {TARGET_SCORE} / Two-Point Rule : {'ON' if TWO_POINT_RULE else 'OFF'}",
        ]
        for i, t in enumerate(lines):
            surf.blit(FONT_S.render(t, True, (70,70,70)), (20, SCREEN_H-90 + i*22))
        surf.blit(FONT_M.render("© BJC - Badminton Junkies Crew", True, (80,80,80)), (20, SCREEN_H-40))

    def handle_event(self, evt):
        self.start_btn.handle_event(evt, self.go_game)
        self.howto_btn.handle_event(evt, self.go_howto)
        self.quit_btn.handle_event(evt, self.quit_game)

class HowToScene(Scene):
    def __init__(self, back_menu):
        self.back_menu = back_menu
        self.title = Label("Instructions for operation", (SCREEN_W//2, 90))
        self.back_btn = Button("Back", (SCREEN_W//2, SCREEN_H-80), size=(160, 56))
        self.lines = [
            "Arrow keys ←/→/↑/↓ : Move left/right/forward/back",
            "Enter              : Start serve",
            "Space              : Smash (faster return)",
            "",
            "Serve rules:",
            "- Point-winner serves next",
            "- Odd score: left; even: right",
        ]
        self.text_surfs = [FONT_S.render(t, True, (40,40,40)) for t in self.lines]

    def update(self, dt):
        self.back_btn.update(pygame.mouse.get_pos())

    def draw(self, surf):
        surf.fill((248,250,253))
        self.title.draw(surf)
        x = SCREEN_W//2 - 280; y = 160; box_w = 560; line_h = 34
        box = pygame.Rect(x-20, y-20, box_w+40, line_h*len(self.text_surfs)+40)
        pygame.draw.rect(surf, (235,240,248), box, border_radius=16)
        pygame.draw.rect(surf, BLACK, box, 2, border_radius=16)
        for i, s in enumerate(self.text_surfs): surf.blit(s, (x, y + i*line_h))
        self.back_btn.draw(surf)

    def handle_event(self, evt):
        self.back_btn.handle_event(evt, self.back_menu)
        if evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
            self.back_menu()

# ------------------------------------------------------------------------------
# Game Scene
# ------------------------------------------------------------------------------
class GameScene(Scene):
    def __init__(self, go_menu, go_gameover):
        self.court_h = 780
        self.court_w = int(self.court_h / 1.5)
        x = (SCREEN_W - self.court_w) // 2
        y = (SCREEN_H - self.court_h) // 2
        self.court = pygame.Rect(x, y, self.court_w, self.court_h)
        self.cy = self.court.centery
        self.cx = self.court.centerx

        self.info = Label("", (SCREEN_W//2, 40), font=FONT_M)
        self.go_menu, self.go_gameover = go_menu, go_gameover

        self.shuttle = Shuttle(self.court)
        self.p_bottom = Player("bottom", self.court, is_human=True)
        self.p_top    = Player("top",    self.court, is_human=False)

        self.score = {"top": 0, "bottom": 0}
        self.server = "bottom"
        self.rally_on = False
        self.ai_serve_timer = 0.0

        self.sf_time = 0.0
        self.last_scored = None
        self.last_hitter = None

        self.diff_name = "normal"
        self.diff = DIFFICULTY[self.diff_name]
        self.info.set_text(f"Difficulty: {self.diff_name.upper()}  |  Enter to serve")

        # ----------------------------------------------------------------------
        # Dynamic Sound: we'll try to load a few known paths; if missing, keep silent.
        # This keeps the game playable without asset setup.
        # ----------------------------------------------------------------------
        self.snd_receive = self._try_sound([
            "badminton-83559.mp3"
        ])
        self.snd_smash   = self._try_sound([
            "table-smash-47690.mp3"
        ])
        self.snd_fail    = self._try_sound([
            "cartoon-fail-trumpet-278822.mp3"
        ])
        self.snd_win     = self._try_sound([
            "you-win-sequence-1-183948.mp3"
        ])
        for s, vol in [(self.snd_receive,0.75),(self.snd_smash,0.85),(self.snd_fail,0.85),(self.snd_win,0.9)]:
            (s and s.set_volume(vol))

        self.reset_serve()

    def _try_sound(self, candidates):
        for p in candidates:
            try:
                return pygame.mixer.Sound(p)
            except Exception:
                continue
        return None

    def play_receive(self): self.snd_receive and self.snd_receive.play()
    def play_smash(self):   self.snd_smash   and self.snd_smash.play()
    def play_fail(self):    self.snd_fail    and self.snd_fail.play()
    def play_win(self):     self.snd_win     and self.snd_win.play()

    # --- Court helpers ---------------------------------------------------------
    def _half_rect(self, side):
        r = self.court.copy(); r.height //= 2
        if side == "bottom": r.top = self.cy
        return r

    def _side_spot(self, side, which):
        half = self._half_rect(side)
        dx = int(half.width * 0.25)
        if side == "bottom":
            x = half.centerx + (dx if which == "right" else -dx)
        else:
            x = half.centerx - (dx if which == "right" else -dx)
        return int(x), int(half.centery)

    def _serve_spot(self, side):
        even = (self.score[side] % 2 == 0)
        return self._side_spot(side, "right" if even else "left")

    def _receive_spot(self, server_side):
        opp = "top" if server_side == "bottom" else "bottom"
        even = (self.score[server_side] % 2 == 0)
        return self._side_spot(opp, "right" if even else "left")

    def _place_for_serve(self):
        # Place server and receiver at the correct diagonal service boxes;
        # keep the shuttle slightly offset so it doesn't overlap the server's racket.
        sx, sy = self._serve_spot(self.server)
        rx, ry = self._receive_spot(self.server)
        svr = self.p_bottom if self.server == "bottom" else self.p_top
        rcv = self.p_top    if self.server == "bottom" else self.p_bottom
        svr.pos[:] = [sx, sy]; rcv.pos[:] = [rx, ry]
        self.shuttle.pos[:] = [sx, sy - 36] if self.server == "bottom" else [sx, sy + 36]
        self.shuttle.vel[:] = [0.0, 0.0]

    def reset_serve(self):
        self.rally_on = False
        self._place_for_serve()

        self.last_hitter = None
        self.p_bottom.swing_pressed = False
        self.p_top.swing_pressed = False
        self.p_bottom.last_hit_time = -999.0
        self.p_top.last_hit_time = -999.0
        if self.server == "bottom":
            self.info.set_text("Wait for serve: BOTTOM — Enter")
            self.ai_serve_timer = 0.0
        else:
            self.info.set_text("Wait for serve: TOP — AI soon")
            self.ai_serve_timer = 0.6

    def start_rally(self):
        self.rally_on = True
        sp = BASE_HIT_SPEED + 80
        self.shuttle.vel[:] = [0.0, -sp] if self.server == "bottom" else [0.0, sp]
        self.last_hitter = self.server
        self.info.set_text("Rally in progress")
        dbg("Rally start by", self.server)

    def side_of_y(self, y):
        return "top" if y < self.cy else "bottom"

    def award_point(self, winner, reason):
        # ----------------------------------------------------------------------
        # Dynamic Sound: scoring feedback
        # ----------------------------------------------------------------------
        self.score[winner] += 1
        (self.play_win() if winner == "bottom" else self.play_fail())
        self.last_scored = winner
        self.sf_time = SCORE_FLASH_DUR
        self.server = winner
        dbg("Point:", winner, "by", reason, "| score:", self.score)

        if self.is_game_over():
            w = "TOP" if self.score["top"] > self.score["bottom"] else "BOTTOM"
            self.go_gameover(dict(self.score), reason, w)
            return
        self.reset_serve()

    def is_game_over(self):
        t, b = self.score["top"], self.score["bottom"]
        lead, mx = abs(t-b), max(t,b)
        return (mx >= TARGET_SCORE and (lead >= 2 if TWO_POINT_RULE else True))

    def _try_hit(self, player, now):
        if self.last_hitter == player.side and self.side_of_y(self.shuttle.pos[1]) == player.side:
            return
        if not player.can_hit(now, self.shuttle):
            return

        # ----------------------------------------------------------------------
        # Shuttlecock Trajectory Algorithm (contact resolution)
        # - Choose a base speed (smash gets a bonus).
        # - Aim roughly toward opponent's current x-position.
        # - Enforce a minimum vertical speed so the shuttle actually crosses net.
        # - Nudge shuttle forward along the new velocity to avoid immediate re-hit.
        # ----------------------------------------------------------------------
        is_smash = player.swing_pressed
        opp = self.p_top if player.side == "bottom" else self.p_bottom
        target_x = opp.pos[0]
        nx = max(-1.0, min(1.0, (target_x - self.shuttle.pos[0]) / 120.0))

        power = BASE_HIT_SPEED + (POWER_HIT_BONUS if is_smash else 0.0)
        vy_sign = -1.0 if player.side == "bottom" else 1.0

        vx = power * 0.6 * nx
        vy = power * vy_sign
        if abs(vy) < MIN_VY_AFTER_HIT:
            vy = MIN_VY_AFTER_HIT * vy_sign

        self.shuttle.vel[:] = [vx, vy]

        sp = math.hypot(vx, vy)
        if sp > 1e-6:
            self.shuttle.pos[0] += (vx / sp) * CROSS_NUDGE_PX
            self.shuttle.pos[1] += (vy / sp) * CROSS_NUDGE_PX

        player.last_hit_time = now
        self.last_hitter = player.side

        if player.is_human:
            self.play_smash() if is_smash else self.play_receive()

    def update(self, dt):
        now = pygame.time.get_ticks() / 1000.0

        keys = pygame.key.get_pressed()

        if not self.rally_on:
            if self.server == "top":
                self.ai_serve_timer -= dt
                if self.ai_serve_timer <= 0:
                    self.start_rally()
            return

        # ------------------ Shuttle Update (Trajectory) -----------------------
        self.shuttle.update(dt)

        self.p_bottom.swing_pressed = keys[pygame.K_SPACE]
        self.p_bottom.update(dt, self.shuttle, self.diff)
        self.p_top.update(dt, self.shuttle, self.diff)

        if self.side_of_y(self.shuttle.pos[1]) == "bottom":
            self._try_hit(self.p_bottom, now); self._try_hit(self.p_top, now)
        else:
            self._try_hit(self.p_top, now); self._try_hit(self.p_bottom, now)

        # ----------------------------------------------------------------------
        # Out-of-bounds & Line Calls (rules):
        # - If shuttle passes left/right beyond outer boundary -> side-out: point to opponent of last hitter.
        # - If shuttle passes top/bottom beyond outer boundary -> baseline-out: point to last hitter.
        # - If the shuttle touches side boundary line bands -> treat as OUT (side line).
        # - Net crossing is represented by the center horizontal line visually;
        #   we don't collide with the "net" (arcade-style), we only ensure shots
        #   have sufficient vertical speed to reach the other half.
        # ----------------------------------------------------------------------
        cx, cy = self.shuttle.pos
        line_w = 6

        if (cx < self.court.left or cx > self.court.right or cy < self.court.top or cy > self.court.bottom):
            if cx < self.court.left or cx > self.court.right:
                hitter = self.last_hitter or self.server
                self.award_point("top" if hitter == "bottom" else "bottom", "Side out")
                return
            self.award_point(self.last_hitter or self.server, "Baseline out")
            return

        on_left  = (self.court.left <= cx <= self.court.left + line_w)
        on_right = (self.court.right - line_w <= cx <= self.court.right)
        if on_left or on_right:
            hitter = self.last_hitter or self.server
            self.award_point("top" if hitter == "bottom" else "bottom", "Side line")
            return

        # Score flash timer (animates color pulse on the scoreboard)
        if self.sf_time > 0:
            self.sf_time = max(0.0, self.sf_time - dt)

    def draw(self, surf):
        # ----------------------------------------------------------------------
        # Dynamic Visuals:
        # - Clean court with thick outer boundary and a central "net" line.
        # - Auxiliary guide lines make the court feel more detailed.
        # - Player sprites are circles with racket radius rings.
        # - Scoreboard flashes on point: color pulses to highlight updates.
        # ----------------------------------------------------------------------
        surf.fill((245, 250, 255))
        self.info.draw(surf)

        MAIN_W = 6
        SUB_W  = 3
        pygame.draw.rect(surf, BLACK, self.court, width=MAIN_W, border_radius=18)
        pygame.draw.line(surf, BLACK, (self.court.left, self.cy), (self.court.right, self.cy), MAIN_W)

        top_y, bot_y = self.court.top, self.court.bottom
        gap_top  = self.cy - top_y
        gap_bot  = bot_y - self.cy
        ys = [
            int(self.cy - gap_top/4),
            int(top_y + gap_top/4),
            int(self.cy + gap_bot/4),
            int(bot_y - gap_bot/4),
        ]
        for y in ys:
            pygame.draw.line(surf, (128,128,128), (self.court.left, y), (self.court.right, y), SUB_W)
        pygame.draw.line(surf, (128,128,128), (self.cx, self.court.top), (self.cx, self.court.bottom), SUB_W)

        self.p_top.draw(surf); self.p_bottom.draw(surf); self.shuttle.draw(surf)

        board = pygame.Rect(self.court.right + 10, self.court.centery - 30, 120, 60)
        pygame.draw.rect(surf, WHITE, board, border_radius=12)
        pygame.draw.rect(surf, BLACK, board, 2, border_radius=12)

        if self.sf_time > 0:
            t = 1.0 - (self.sf_time / SCORE_FLASH_DUR)
            ease = 0.5 - 0.5 * math.cos(math.pi * t)  # smooth in/out
            u = ease if ease <= 0.5 else 1.0 - (ease - 0.5) * 2
            u = max(0.0, min(1.0, u)) * 2.0
            col = tuple(int((1-u)*0 + u*c) for c in SCORE_FLASH_COL)
        else:
            col = BLACK

        txt = FONT_M.render(f"{self.score['top']} : {self.score['bottom']}", True, col)
        surf.blit(txt, (board.centerx - txt.get_width()//2, board.centery - txt.get_height()//2))

        # Help line (quick reference for controls)
        help_line = "←/→/↑/↓ Move | Enter Serve | Space Smash | ESC Menu"
        hsurf = FONT_S.render(help_line, True, (80,80,80))
        surf.blit(hsurf, (SCREEN_W//2 - hsurf.get_width()//2, SCREEN_H - 36))

    def handle_event(self, evt):
        if evt.type == pygame.KEYDOWN:
            if evt.key == pygame.K_ESCAPE:
                self.go_menu()
            elif evt.key == pygame.K_r:
                self.reset_serve()
            elif evt.key == KEY_SERVE and (not self.rally_on) and (self.server == "bottom"):
                self.start_rally()

# ------------------------------------------------------------------------------
# Game Over Scene
# ------------------------------------------------------------------------------
class GameOverScene(Scene):
    def __init__(self, score, reason, winner, go_menu, go_retry):
        self.title  = Label("GAME OVER", (SCREEN_W//2, 120))
        self.detail = Label(f"Reason: {reason} | Winner: {winner} | TOP {score['top']} : {score['bottom']} BOTTOM",
                            (SCREEN_W//2, 180), font=FONT_M)
        self.menu_btn = Button("Back to Menu", (SCREEN_W//2 - 150, 320))
        self.retry_btn = Button("Retry", (SCREEN_W//2 + 150, 320))
        self.go_menu, self.go_retry = go_menu, go_retry

    def update(self, dt):
        m = pygame.mouse.get_pos()
        self.menu_btn.update(m); self.retry_btn.update(m)

    def draw(self, surf):
        surf.fill(WHITE)
        self.title.draw(surf); self.detail.draw(surf)
        self.menu_btn.draw(surf); self.retry_btn.draw(surf)

    def handle_event(self, evt):
        self.menu_btn.handle_event(evt, self.go_menu)
        self.retry_btn.handle_event(evt, self.go_retry)

# ------------------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------------------
def main():
    FPS = 60
    current = {"scene": None}

    def to_menu():
        current["scene"] = MenuScene(to_game, to_howto, lambda: (pygame.quit(), sys.exit()))

    def to_game():
        current["scene"] = GameScene(to_menu, to_gameover)

    def to_howto():
        current["scene"] = HowToScene(to_menu)

    def to_gameover(score, reason, winner):
        current["scene"] = GameOverScene(score, reason, winner, to_menu, to_game)

    to_menu()

    while True:
        dt = clock.tick(FPS) / 1000.0
        for evt in pygame.event.get():
            if evt.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            current["scene"].handle_event(evt)
        current["scene"].update(dt)
        current["scene"].draw(screen)
        pygame.display.flip()

if __name__ == "__main__":
    main()
