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
        self.info = Label("게임 화면 (스페이스: 일시정지/메뉴)", center=(WIDTH//2, 40), font=FONT_M)
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
        # 코트 느낌 라인
        pygame.draw.rect(surf, (180,220,255), pygame.Rect(80,80, WIDTH-160, HEIGHT-160), width=6, border_radius=18)
        pygame.draw.line(surf, (150,180,255), (WIDTH//2, 80), (WIDTH//2, HEIGHT-80), width=4)  # 중앙선(네트 느낌)
        # 셔틀콕(데모)
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
