import pygame
import sys

pygame.init()
WIDTH, HEIGHT = 960, 540
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("BJC - Badminton Junkies Crew")
clock = pygame.time.Clock()
FPS = 60

# 색/폰트
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY  = (200, 200, 200)
PRIMARY = (30, 144, 255)

FONT_L = pygame.font.SysFont("malgungothic", 48)  # 한글 폰트(윈도우 기준)
FONT_M = pygame.font.SysFont("malgungothic", 28)

# ---------- UI 위젯 ----------
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

# ---------- 씬 시스템 ----------
class Scene:
    def update(self, dt): ...
    def draw(self, surf): ...
    def handle_event(self, event): ...

class MenuScene(Scene):
    def __init__(self, go_to_game):
        self.title = Label("TEAM BJC - Badminton Junkies Crew", center=(WIDTH//2, 120))
        self.start_btn = Button("게임 시작", center=(WIDTH//2, 260))
        self.quit_btn  = Button("종료", center=(WIDTH//2, 340))
        self.go_to_game = go_to_game

    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self.start_btn.update(mouse_pos)
        self.quit_btn.update(mouse_pos)

    def draw(self, surf):
        surf.fill(WHITE)
        self.title.draw(surf)
        self.start_btn.draw(surf)
        self.quit_btn.draw(surf)

        # 하단 크레딧
        credit = FONT_M.render("© BJC - Badminton Junkies Crew", True, (80,80,80))
        surf.blit(credit, (20, HEIGHT-40))

    def handle_event(self, event):
        self.start_btn.handle_event(event, self.go_to_game)
        self.quit_btn.handle_event(event, lambda: sys.exit(0))

class GameScene(Scene):
    def __init__(self, go_to_menu):
        self.go_to_menu = go_to_menu
        self.info = Label("", center=(WIDTH//2, 40), font=FONT_M)
        # 예시: 간단한 셔틀콕 표시용
        self.shuttle_pos = [WIDTH//2, HEIGHT//2]
        self.vel = [200, 120]  # px/s
        self.radius = 10
    
    def update(self, dt):
        # 셔틀콕 데모 이동
        self.shuttle_pos[0] += self.vel[0] * dt
        self.shuttle_pos[1] += self.vel[1] * dt
        # 벽 반사
        if self.shuttle_pos[0] < self.radius or self.shuttle_pos[0] > WIDTH - self.radius:
            self.vel[0] *= -1
        if self.shuttle_pos[1] < self.radius or self.shuttle_pos[1] > HEIGHT - self.radius:
            self.vel[1] *= -1

    def draw(self, surf):
        surf.fill((245, 250, 255))
        self.info.draw(surf)

        # ===== 스타일 통일 =====
        MAIN_LINE_COLOR = (0, 0, 0)  # 바깥 코트 테두리 & 가로 중앙선
        MAIN_LINE_W     = 6

        SUB_LINE_COLOR  = (128, 128, 128)  # 보조선(위/아래 x/4 두 줄 + 세로 중앙선)
        SUB_LINE_W      = 3

        # ===== 코트 크기/위치 =====
        COURT_H = 780
        COURT_W = int(COURT_H / 1.5)  # 현재 네가 둔 비율 유지
        court_x = (WIDTH  - COURT_W) // 2
        court_y = (HEIGHT - COURT_H) // 2
        court_rect = pygame.Rect(court_x, court_y, COURT_W, COURT_H)

        # 바깥 코트 테두리
        pygame.draw.rect(surf, MAIN_LINE_COLOR, court_rect, width=MAIN_LINE_W, border_radius=18)

        # ===== 중앙선(가로) - 코트 세로 중앙 y =====
        cy = court_rect.centery
        pygame.draw.line(
            surf, MAIN_LINE_COLOR,
            (court_rect.left,  cy),
            (court_rect.right, cy),
            width=MAIN_LINE_W
        )

        # ===== 아래 코트(x = 중앙선~아래 테두리 거리)에서 x/4 지점 두 줄 =====
        bottom_y = court_rect.bottom
        x_bottom = bottom_y - cy

        y_down_from_center = int(cy + x_bottom / 4)      # 중앙선에서 x/4만큼 ↓
        y_up_from_bottom   = int(bottom_y - x_bottom / 4) # 아래 테두리에서 x/4만큼 ↑

        pygame.draw.line(surf, SUB_LINE_COLOR, (court_rect.left,  y_down_from_center), (court_rect.right, y_down_from_center), width=SUB_LINE_W)
        pygame.draw.line(surf, SUB_LINE_COLOR, (court_rect.left,  y_up_from_bottom),   (court_rect.right, y_up_from_bottom),   width=SUB_LINE_W)

        # ===== 위 코트(x = 중앙선~위 테두리 거리)에서 x/4 지점 두 줄 =====
        top_y = court_rect.top
        x_top = cy - top_y

        y_up_from_center = int(cy - x_top / 4)        # 중앙선에서 x/4만큼 ↑
        y_down_from_top  = int(top_y + x_top / 4)     # 위 테두리에서 x/4만큼 ↓

        pygame.draw.line(surf, SUB_LINE_COLOR, (court_rect.left,  y_up_from_center), (court_rect.right, y_up_from_center), width=SUB_LINE_W)
        pygame.draw.line(surf, SUB_LINE_COLOR, (court_rect.left,  y_down_from_top),  (court_rect.right, y_down_from_top),  width=SUB_LINE_W)

        # ===== 세로 중앙선 =====
        center_x = court_rect.centerx
        pygame.draw.line(
            surf, SUB_LINE_COLOR,
            (center_x, court_rect.top),
            (center_x, court_rect.bottom),
            width=SUB_LINE_W
        )

        # 셔틀(데모)
        pygame.draw.circle(surf, (30,144,255), (int(self.shuttle_pos[0]), int(self.shuttle_pos[1])), self.radius)


    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.go_to_menu()

# ---------- 앱 실행 ----------
def main():
    # 씬 전환 콜백 정의
    current_scene = {"scene": None}
    def go_to_menu():
        current_scene["scene"] = MenuScene(go_to_game)
    def go_to_game():
        current_scene["scene"] = GameScene(go_to_menu)

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
