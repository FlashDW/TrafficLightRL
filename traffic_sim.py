import random
import os
import pygame

class Car:
    def __init__(self, lane, distance, sim):
        self.lane = lane
        self.distance = distance
        self.sim = sim
        self.passed_stop_block = False
        self.max_speed = sim.speed_limit_px - 10
        self.accel = sim.max_car_accel
        self.decel = sim.max_car_decel + 10
        self.speed = self.max_speed
        self.stop_pos = sim.stop_posD if self.lane in ["du", "rl"] else sim.stop_posU
        self.crashed = False
        self.alpha = 255
        
        
    def stopping_distance(self):
        if self.decel <= 0:
            return float('inf')
        return pow(self.speed, 2)/(2.0*self.decel)
        
    def update(self, dt, light, lead=None):
        if self.crashed == False:
            #update the wait time
            if self.distance < self.stop_pos and self.speed < self.max_speed:
                self.sim.total_wait_time += dt
    
            target_speed = self.max_speed
    
            #if the lights red, stop
            distance_to_stop = self.stop_pos - self.distance
            if light == 'r':
                if distance_to_stop > 0:
                    cushion = 5.0
                    if distance_to_stop <= self.stopping_distance() + cushion:
                        target_speed = 0.0
                
    
    
            #match the speed of the car ahead
            if lead is not None:
                gap = (lead.distance - self.sim.car_length) - self.distance
                safe_time = 0.6
                desired_gap = safe_time * self.speed + self.sim.car_spacing
                if gap <= desired_gap + 2.0:
                    target_speed = min(target_speed, lead.speed)
                else:
                    k_p = 1.8
                    closing = k_p * (gap - desired_gap)
                    target_speed = min(target_speed, min(self.max_speed, lead.speed + closing))
    
                #if too close to car ahead, slow down
                if lead.distance - self.distance < (self.sim.car_length + self.sim.car_spacing):
                    target_speed = 0.0
    
            #if the lights yellow, go slow.
            if light == 'y':
                if target_speed > self.max_speed/4 and self.distance < self.stop_pos:
                    target_speed = self.max_speed/4
    
            # accelerate or decelerate
            if self.speed < target_speed:
                self.speed = min(self.speed + self.accel * dt, target_speed, self.max_speed)
            else:
                self.speed = max(self.speed - self.decel * dt, target_speed, 0.0)
    
            if self.speed < 1e-3:
                self.speed = 0.0
    
            self.distance += self.speed * dt


class TrafficSim:
    car_img = None
    cached_cars = {}
    fonts = {}
    def __init__(self, s, r, seed=None):
        # 1 - normal
        # 2 - rush hour
        # 3 - big event
        self.scenario = s

        self.reward_function = r
        
        if seed is not None:
            random.seed(seed)

        self.clock = None
        self.font = None
        self.font1 = None
        self.font2 = None

        self.screen_width = 900
        self.screen_height = 900

        #-----caches images and fonts to avoid reloading multiple times-----
        if TrafficSim.car_img is None or not TrafficSim.fonts:
            pygame.init()
            pygame.display.set_mode((1, 1), pygame.HIDDEN)

            if TrafficSim.car_img is None:
                script_dir = os.path.dirname(__file__)

                car_path = os.path.join(script_dir, "car.png")

                TrafficSim.car_img = pygame.image.load(car_path).convert_alpha()

                lane_width = 75
                car_img = TrafficSim.car_img
                car_width = lane_width * 0.9
                car_length = car_width * (car_img.get_width() / car_img.get_height())

                car_right = pygame.transform.scale(car_img, (int(car_length), int(car_width)))
                car_left = pygame.transform.rotate(car_right, 180)
                car_up = pygame.transform.rotate(car_right, 90)
                car_down = pygame.transform.rotate(car_right, -90)

                def make_red(img):
                    red = img.copy()
                    red.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    return red
                
                TrafficSim.cached_cars = {
                    "right": car_right,
                    "left": car_left,
                    "up": car_up,
                    "down": car_down,
                    "right_red": make_red(car_right),
                    "left_red": make_red(car_left),
                    "up_red": make_red(car_up),
                    "down_red": make_red(car_down),
                }

            if not TrafficSim.fonts:
                TrafficSim.fonts = {
                    'main': pygame.font.SysFont('couriernew', 20),
                    'small': pygame.font.SysFont('couriernew', 15),
                    'large': pygame.font.SysFont('couriernew', 50)
                }

            pygame.display.quit()


        self.font = TrafficSim.fonts['main']
        self.font1 = TrafficSim.fonts['small']
        self.font2 = TrafficSim.fonts['large']
        self.car_img = TrafficSim.car_img
        self.car_img_right = TrafficSim.cached_cars["right"]
        self.car_img_left = TrafficSim.cached_cars["left"]
        self.car_img_up = TrafficSim.cached_cars["up"]
        self.car_img_down = TrafficSim.cached_cars["down"]

        self.car_img_right_red = TrafficSim.cached_cars["right_red"]
        self.car_img_left_red = TrafficSim.cached_cars["left_red"]
        self.car_img_up_red = TrafficSim.cached_cars["up_red"]
        self.car_img_down_red = TrafficSim.cached_cars["down_red"]
        self.car_img_width, self.car_img_height = self.car_img.get_size()


        #intersection
        self.road_color = (50, 50, 50)
        self.line_color = (255, 230, 0)
        self.white = (230, 230, 230)
        self.lane_width = 75
        self.line_thickness = 2
        self.line_spacing = 4  #space between the two yellow lines
        self.crossing_width = 30
        self.stop_block_width = 10
        self.crossing_stop_block_spacing = 20
        self.num_cross_blocks = 7
        self.cross_block_spacing = 10
        self.cross_block_width = (self.lane_width*2 - (self.cross_block_spacing * (self.num_cross_blocks+1))) // self.num_cross_blocks

        #lights
        self.light_width = 30
        self.light_height = 30
        self.light_box_buffer_side = 5
        self.light_box_buffer_top = 5
        self.light_circle_spacing = 5
        self.light_box_color = (40, 40, 40)
        self.red_b = (255, 0, 0)
        self.yellow_b = (255, 255, 0)
        self.green_b = (0, 255, 0)
        self.red_d = (100, 0, 0)
        self.yellow_d = (100, 100, 0)
        self.green_d = (0, 100, 0)
        self.light_road_spacing = 5
        self.light_box_width = self.light_box_buffer_side*2 + self.light_width
        self.light_box_height = self.light_box_buffer_top*2 + self.light_height*3 + self.light_circle_spacing*2

        #car sizing and spacing

        self.car_width = self.lane_width * 0.9
        self.car_length = self.car_width * (self.car_img_width / self.car_img_height)
        self.car_spacing = 10
        self.speed_limit_real = 25.0 #miles per hour
        self.average_car_length = 15.0 #feet
        self.px_per_ft = self.car_length / self.average_car_length
        self.speed_limit = self.speed_limit_real * (5280.0 / 3600.0) #feet per second
        self.speed_limit_px = round(self.speed_limit * self.px_per_ft)
        self.average_accel = 9.8 #feet per second
        self.max_car_accel = round(self.px_per_ft * self.average_accel)
        self.average_decel = 23 #feet per second
        self.max_car_decel = round(self.px_per_ft * self.average_decel)

        #resize car image
        self.car_img_right = pygame.transform.scale(self.car_img, (self.car_length, self.car_width))

        #car images with different rotations
        self.car_img_down = pygame.transform.rotate(self.car_img_right, -90)
        self.car_img_left = pygame.transform.rotate(self.car_img_right, 180)
        self.car_img_up = pygame.transform.rotate(self.car_img_right, 90)

        self.car_img_right_red = self.car_img_right.copy()
        self.car_img_right_red.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.car_img_left_red = self.car_img_left.copy()
        self.car_img_left_red.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.car_img_down_red = self.car_img_down.copy()
        self.car_img_down_red.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.car_img_up_red = self.car_img_up.copy()
        self.car_img_up_red.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        #stop positions
        self.stop_posD = self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing
        self.stop_posU = self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing - self.car_length

        #Lanes
        self.lr = []
        self.rl = []
        self.ud = []
        self.du = []

        self.lanes = [self.lr, self.rl, self.ud, self.du]

        self.crashed = []

        self.total_wait_time = 0.0
        self.num_cars = 0
        self.average_wait_time = 0.0

        self.num_crashes = 0
        self.total_time = 0
        self.trial_time = 60
        self.cars_passed = 0
        self.prev_passed = 0

        #lights
        self.vert_light = "g"
        self.horiz_light = "g"

        self.prev_wait_time = 0
        self.prev_crashes = 0

    def init_pygame(self):
        #initialize pygame
        pygame.init()
        self.clock = pygame.time.Clock()

        self.screen_width = 900
        self.screen_height = 900
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Traffic Light Reinforcement Learning Project")

    def createCar(self):
        if self.scenario == 1:
            if random.random() > 0.99:
                x = random.random()
                if x < 0.25:
                    self.lr.append(Car("lr", len(self.lr)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                elif x < 0.5:
                    self.rl.append(Car("rl", len(self.rl)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
                elif x < 0.75:
                    self.ud.append(Car("ud", len(self.ud)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                else:
                    self.du.append(Car("du", len(self.du)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
        elif self.scenario == 2:
            if random.random() > 0.90:
                x = random.random()
                if x < 0.25:
                    self.lr.append(Car("lr", len(self.lr)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                elif x < 0.5:
                    self.rl.append(Car("rl", len(self.rl)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
                elif x < 0.75:
                    self.ud.append(Car("ud", len(self.ud)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                else:
                    self.du.append(Car("du", len(self.du)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
        elif self.scenario == 3:
            if random.random() > 0.99:
                x = random.random()
                if x < 0.25:
                    self.lr.append(Car("lr", len(self.lr)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                elif x < 0.5:
                    self.ud.append(Car("ud", len(self.ud)*(self.car_length + self.car_spacing) * -1 - self.car_length - 300, self))
                    self.num_cars += 1
                elif x < 0.75:
                    self.du.append(Car("du", len(self.du)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
            if random.random() > 0.85:
                x = random.random()
                if x < 0.25:
                    self.rl.append(Car("rl", len(self.rl)*(self.car_length + self.car_spacing) * -1 - 300, self))
                    self.num_cars += 1
            
    def checkForCrashes(self):
        car_rects = []

        def get_car_rect(car):
            if car.lane == 'lr':
                x = car.distance
                y = self.screen_height/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
            elif car.lane == 'rl':
                x = self.screen_width - car.distance
                y = self.screen_height/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
            elif car.lane == "ud":
                x = self.screen_width/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
                y = car.distance
            else:
                x = self.screen_width/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
                y = self.screen_height - car.distance

            if car.lane in ['rl', 'lr']:
                return pygame.Rect(x, y, self.car_length, self.car_width)
            else:
                return pygame.Rect(x, y, self.car_width, self.car_length)

        for lane in self.lanes:
            for car in lane:
                if not car.crashed and car.distance > 0:
                    car_rects.append((get_car_rect(car), car))

        for i in range(len(car_rects)):
            rect1, car1 = car_rects[i]
            for j in range(i+1, len(car_rects)):
                rect2, car2 = car_rects[j]
                
                #skip if both cars are far from the intersection (saves time)
                if abs(rect1.centerx - rect2.centerx) > 200 or abs(rect1.centery - rect2.centery) > 200:
                    continue

                if rect1.colliderect(rect2):
                    if not car1.crashed or not car2.crashed:
                        car1.crashed = car2.crashed = True

                        self.crashed.append(car1)
                        self.crashed.append(car2)
                        
                        if car1.lane == 'lr' and car1 in self.lr:
                            self.lr.remove(car1)
                        elif car1.lane == 'rl' and car1 in self.rl:
                            self.rl.remove(car1)
                        elif car1.lane == 'ud' and car1 in self.ud:
                            self.ud.remove(car1)
                        elif car1 in self.du:
                            self.du.remove(car1)

                        if car2.lane == 'lr' and car2 in self.lr:
                            self.lr.remove(car2)
                        elif car2.lane == 'rl' and car2 in self.rl:
                            self.rl.remove(car2)
                        elif car2.lane == 'ud' and car2 in self.ud:
                            self.ud.remove(car2)
                        elif car2 in self.du:
                            self.du.remove(car2)
                        self.num_crashes += 1        

    def reset_vals(self):
        self.prev_wait_time = 0
        self.prev_crashes = 0
        
        #lights
        self.vert_light = "r"
        self.horiz_light = "r"
        
        #Lanes
        self.lr = []
        self.rl = []
        self.ud = []
        self.du = []
        
        self.lanes = [self.lr, self.rl, self.ud, self.du]
        
        self.crashed = []
        
        self.total_wait_time = 0.0
        self.num_cars = 0
        self.average_wait_time = 0.0
        
        self.num_crashes = 0
        self.total_time = 0
        self.cars_passed = 0

    def draw_screen(self):
        #clear screen
        self.screen.fill((0, 0, 0))

        vr = self.red_d
        vy = self.yellow_d
        vg = self.green_d

        hr = self.red_d
        hy = self.yellow_d
        hg = self.green_d

        if self.vert_light == "r":
            vr = self.red_b
        elif self.vert_light == "y":
            vy = self.yellow_b
        elif self.vert_light == "g":
            vg = self.green_b

        if self.horiz_light == "r":
            hr = self.red_b
        elif self.horiz_light == "y":
            hy = self.yellow_b
        elif self.horiz_light == "g":
            hg = self.green_b
        
        #draw intersection
        
        #draw roads
        #verticle road
        pygame.draw.rect(self.screen, self.road_color, (self.screen_width/2 - self.lane_width, 0, self.lane_width*2, self.screen_height))
        
        #horizontal road
        pygame.draw.rect(self.screen, self.road_color, (0, self.screen_height/2 - self.lane_width, self.screen_width, self.lane_width*2))
        
        #yellow lines
        #verticle
        
        #lower
        pygame.draw.rect(self.screen, self.line_color, (self.screen_width/2-self.line_spacing/2-self.line_thickness, self.screen_height/2 + self.lane_width + self.crossing_width + self.stop_block_width + self.crossing_stop_block_spacing, self.line_thickness, self.screen_height))
        pygame.draw.rect(self.screen, self.line_color, (self.screen_width/2+self.line_spacing/2, self.screen_height/2 + self.lane_width + self.crossing_width + self.stop_block_width + self.crossing_stop_block_spacing, self.line_thickness, self.screen_height))
        
        #upper
        pygame.draw.rect(self.screen, self.line_color, (self.screen_width/2-self.line_spacing/2-self.line_thickness, 0, self.line_thickness, self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing))
        pygame.draw.rect(self.screen, self.line_color, (self.screen_width/2+self.line_spacing/2, 0, self.line_thickness, self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing))
        
        
        #horizontal
        
        #left
        pygame.draw.rect(self.screen, self.line_color, (0, self.screen_height/2-self.line_spacing/2-self.line_thickness, self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing, self.line_thickness))
        pygame.draw.rect(self.screen, self.line_color, (0, self.screen_height/2+self.line_spacing/2, self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing, self.line_thickness))
        
        #right
        pygame.draw.rect(self.screen, self.line_color, (self.screen_height/2 + self.lane_width + self.crossing_width + self.stop_block_width + self.crossing_stop_block_spacing, self.screen_height/2-self.line_spacing/2-self.line_thickness, self.screen_height/2 - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing, self.line_thickness))
        pygame.draw.rect(self.screen, self.line_color, (self.screen_height/2 + self.lane_width + self.crossing_width + self.stop_block_width + self.crossing_stop_block_spacing, self.screen_height/2+self.line_spacing/2, self.screen_height/2 - self.crossing_width - self.stop_block_width - self.crossing_stop_block_spacing, self.line_thickness))
        
        #crosswalk
        #verticle road
        #lower
        for i in range(self.num_cross_blocks):
            pygame.draw.rect(self.screen, self.white, ((self.screen_width//2-self.lane_width + (self.cross_block_spacing*(i+1)) + (self.cross_block_width*i)), self.screen_height//2 + self.lane_width, self.cross_block_width, self.crossing_width))
        
        #upper
        for i in range(self.num_cross_blocks):
            pygame.draw.rect(self.screen, self.white, ((self.screen_width//2-self.lane_width + (self.cross_block_spacing*(i+1)) + (self.cross_block_width*i)), self.screen_height//2 - self.lane_width - self.crossing_width, self.cross_block_width, self.crossing_width))
        
        #horizontal road
        #left
        for i in range(self.num_cross_blocks):
            pygame.draw.rect(self.screen, self.white, (self.screen_width//2 - self.lane_width - self.crossing_width, (self.screen_height//2-self.lane_width + (self.cross_block_spacing*(i+1)) + (self.cross_block_width*i)), self.crossing_width, self.cross_block_width))
        
        #right
        for i in range(self.num_cross_blocks):
            pygame.draw.rect(self.screen, self.white, (self.screen_width//2 + self.lane_width, (self.screen_height//2-self.lane_width + (self.cross_block_spacing*(i+1)) + (self.cross_block_width*i)), self.crossing_width, self.cross_block_width))
        
        #stop blocks
        #verticle road
        #lower
        pygame.draw.rect(self.screen, self.white, (self.screen_width/2 + self.line_spacing//2 + self.line_thickness, self.screen_height/2 + self.lane_width + self.crossing_width + self.crossing_stop_block_spacing + self.stop_block_width, self.lane_width - self.line_spacing//2 - self.line_thickness, self.stop_block_width))
        
        #upper
        pygame.draw.rect(self.screen, self.white, (self.screen_width/2 - self.lane_width, self.screen_height/2 - self.lane_width - self.crossing_width - self.crossing_stop_block_spacing - self.stop_block_width*2, self.lane_width - self.line_thickness - self.line_spacing//2, self.stop_block_width))
        
        #horizontal road
        #left
        pygame.draw.rect(self.screen, self.white, (self.screen_height/2 - self.lane_width - self.crossing_width - self.stop_block_width*2 - self.crossing_stop_block_spacing, self.screen_height/2 + self.line_spacing//2 + self.line_thickness, self.stop_block_width, self.lane_width - self.line_spacing//2 - self.line_thickness))
        
        #right
        pygame.draw.rect(self.screen, self.white, (self.screen_height/2 + self.lane_width + self.crossing_width + self.stop_block_width + self.crossing_stop_block_spacing, self.screen_width/2 - self.lane_width, self.stop_block_width, self.lane_width - self.line_thickness - self.line_spacing//2))
        
        #lights
        #bottom right
        #box
        pygame.draw.rect(self.screen, self.light_box_color, (self.screen_width/2 + self.lane_width + self.light_road_spacing, self.screen_height/2 + self.lane_width + self.light_road_spacing, self.light_box_width, self.light_box_height))
        #red
        pygame.draw.ellipse(self.screen, vr, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_top, self.light_width, self.light_height))
        #yellow
        pygame.draw.ellipse(self.screen, vy, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_height + self.light_circle_spacing + self.light_box_buffer_top, self.light_width, self.light_height))
        #green
        pygame.draw.ellipse(self.screen, vg, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_height*2 + self.light_circle_spacing*2 + self.light_box_buffer_top, self.light_width, self.light_height))
        
        #top left
        #box
        pygame.draw.rect(self.screen, self.light_box_color, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_width, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_height, self.light_box_width, self.light_box_height))
        #red
        pygame.draw.ellipse(self.screen, vr, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_width, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_top - self.light_height, self.light_width, self.light_height))
        #yellow
        pygame.draw.ellipse(self.screen, vy, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_width, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_height*2 - self.light_circle_spacing - self.light_box_buffer_top, self.light_width, self.light_height))
        #green
        pygame.draw.ellipse(self.screen, vg, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_width, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_height*3 - self.light_circle_spacing*2 - self.light_box_buffer_top, self.light_width, self.light_height))
        
        #bottom left
        #box
        pygame.draw.rect(self.screen, self.light_box_color, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_height, self.screen_height/2 + self.lane_width + self.light_road_spacing, self.light_box_height, self.light_box_width))
        #red
        pygame.draw.ellipse(self.screen, hr, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_top - self.light_width, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.light_height, self.light_width))
        #yellow
        pygame.draw.ellipse(self.screen, hy, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_top - self.light_width*2 - self.light_circle_spacing, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.light_height, self.light_width))
        #green
        pygame.draw.ellipse(self.screen, hg, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_top - self.light_width*3 - self.light_circle_spacing*2, self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_side, self.light_height, self.light_width))
        
        #top right
        #box
        pygame.draw.rect(self.screen, self.light_box_color, (self.screen_width/2 + self.lane_width + self.light_road_spacing, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_width, self.light_box_height, self.light_box_width))
        #red
        pygame.draw.ellipse(self.screen, hr, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_top, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_height, self.light_height, self.light_width))
        #yellow
        pygame.draw.ellipse(self.screen, hy, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_top + self.light_width + self.light_circle_spacing, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_height, self.light_height, self.light_width))
        #green
        pygame.draw.ellipse(self.screen, hg, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_buffer_top + self.light_width*2 + self.light_circle_spacing*2, self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_buffer_side - self.light_height, self.light_height, self.light_width))
        
        
        #draw cars
        for i in self.lanes:
            for j in range(len(i)):
                if i[j].lane == "du":
                    #screen_width/2 + line_spacing/2 + self.line_thickness + ((lane_width - car_width)/2)
                    car_x = self.screen_width/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
                    self.screen.blit(self.car_img_up, (car_x, self.screen_height - i[j].distance))
                elif i[j].lane == "rl":
                    car_y = self.screen_height/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
                    self.screen.blit(self.car_img_left, (self.screen_width - i[j].distance, car_y))
                elif i[j].lane == "ud":
                    car_x = self.screen_width/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
                    self.screen.blit(self.car_img_down, (car_x, i[j].distance))
                else:
                    car_y = self.screen_height/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
                    self.screen.blit(self.car_img_right, (i[j].distance, car_y))
        
        
        to_remove = []
        #draw crashed cars
        for car in self.crashed:
            if car.lane == "du":
                #screen_width/2 + line_spacing/2 + self.line_thickness + ((lane_width - car_width)/2)
                if car.alpha > 1:
                    alpha_surface = pygame.Surface(self.car_img_up_red.get_size(), pygame.SRCALPHA)
                    alpha_surface.fill((255, 255, 255, car.alpha))
                    x = self.car_img_up_red.copy()
                    x.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    car_x = self.screen_width/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
                    self.screen.blit(x, (car_x, self.screen_height - car.distance))
                    car.alpha -= 4
                else:
                    to_remove.append(car)
            elif car.lane == "rl":
                if car.alpha > 1:
                    alpha_surface = pygame.Surface(self.car_img_left_red.get_size(), pygame.SRCALPHA)
                    alpha_surface.fill((255, 255, 255, car.alpha))
                    x = self.car_img_left_red.copy()
                    x.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    car_y = self.screen_height/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
                    self.screen.blit(x, (self.screen_width - car.distance, car_y))
                    car.alpha -= 4
                else:
                    to_remove.append(car)
            elif car.lane == "ud":
                if car.alpha > 1:
                    alpha_surface = pygame.Surface(self.car_img_down_red.get_size(), pygame.SRCALPHA)
                    alpha_surface.fill((255, 255, 255, car.alpha))
                    x = self.car_img_down_red.copy()
                    x.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    car_x = self.screen_width/2 - self.lane_width/2 - self.line_spacing/8 - self.line_thickness/2 - self.car_width/2
                    self.screen.blit(x, (car_x, car.distance))
                    car.alpha -= 4
                else:
                    to_remove.append(car)
            else:
                if car.alpha > 1:
                    alpha_surface = pygame.Surface(self.car_img_right_red.get_size(), pygame.SRCALPHA)
                    alpha_surface.fill((255, 255, 255, car.alpha))
                    x = self.car_img_right_red.copy()
                    x.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    car_y = self.screen_height/2 + self.lane_width/2 + self.line_spacing/2 + self.line_thickness/2 - self.car_width/2
                    self.screen.blit(x, (car.distance, car_y))
                    car.alpha -= 4
                else:
                    to_remove.append(car)
        
        for car in to_remove:
            self.crashed.remove(car)
        
        
        self.average_wait_time = (self.total_wait_time / self.num_cars) if self.num_cars > 0 else 0.0
        wait_surface = self.font1.render(f"Average wait time per car: {round(self.average_wait_time, 2)} seconds", True, (255, 255, 255))
        self.screen.blit(wait_surface, (10, 10))
        
        crash_surface = self.font.render(f"Crashes: {self.num_crashes}", True, (255, 255, 255))
        self.screen.blit(crash_surface, (10, wait_surface.get_size()[1] + 10))
        
        time_surface = self.font2.render(f"{round(self.trial_time - self.total_time)}", True, (255, 255, 255))
        self.screen.blit(time_surface, (self.screen_width - time_surface.get_size()[0], 0))
        
        #amount of cars in each lane
        num_cars_du_surface = self.font.render(f"{len(self.du)}", True, (255, 255, 255))
        self.screen.blit(num_cars_du_surface, (self.screen_width/2 + self.lane_width + self.light_road_spacing,  self.screen_height/2 + self.lane_width + self.light_road_spacing + self.light_box_height))
        num_cars_rl_surface = self.font.render(f"{len(self.rl)}", True, (255, 255, 255))
        self.screen.blit(num_cars_rl_surface, (self.screen_width/2 + self.lane_width + self.light_road_spacing + self.light_box_height,  self.screen_height/2 - self.lane_width - self.light_road_spacing - num_cars_rl_surface.get_size()[1]))
        num_cars_ud_surface = self.font.render(f"{len(self.ud)}", True, (255, 255, 255))
        self.screen.blit(num_cars_ud_surface, (self.screen_width/2 - self.lane_width - self.light_road_spacing -  num_cars_ud_surface.get_size()[0], self.screen_height/2 - self.lane_width - self.light_road_spacing - self.light_box_height - num_cars_ud_surface.get_size()[1]))
        num_cars_lr_surface = self.font.render(f"{len(self.lr)}", True, (255, 255, 255))
        self.screen.blit(num_cars_lr_surface, (self.screen_width/2 - self.lane_width - self.light_road_spacing - self.light_box_height - num_cars_lr_surface.get_size()[0], self.screen_height/2 + self.lane_width + self.light_road_spacing))
        
        
        #update the display
        pygame.display.flip()

    def run_sim(self):
        self.reset_vals()
        if not pygame.get_init():
            self.init_pygame()
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            self.total_time += dt
            if self.total_time > self.trial_time:
                running = False
        
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            keys_pressed = pygame.key.get_pressed()
            if keys_pressed[pygame.K_q]:
                self.vert_light = "g"
            elif keys_pressed[pygame.K_w]:
                self.vert_light = "y"
            elif keys_pressed[pygame.K_e]:
                self.vert_light = "r"
            elif keys_pressed[pygame.K_a]:
                self.horiz_light = "g"
            elif keys_pressed[pygame.K_s]:
                self.horiz_light = "y"
            elif keys_pressed[pygame.K_d]:
                self.horiz_light = "r"
            
            
            
            self.createCar()
        
            #update cars
            for lane in self.lanes:
                ordered = sorted(lane, key=lambda c: c.distance, reverse=True)
            
                for idx, car in enumerate(ordered):
                    lead = ordered[idx - 1] if idx > 0 else None
                    light = self.horiz_light if car.lane in ["lr", "rl"] else self.vert_light
                    car.update(dt, light, lead)
        
                    
            #pop cars
            for i in self.lanes:
                for j in range(len(i)-1, -1, -1):
                    if i[j].distance > self.screen_height + self.car_length:
                        self.cars_passed += 1
                        print("Car passed!")
                        print(self.cars_passed)
                        i.pop(j)
        
            self.checkForCrashes()

            self.draw_screen()

    def waiting_rew(self):
        return -self.total_wait_time
    
    def passed_car_rew(self):
        return self.cars_passed * 50
                    
    def step_sim(self, dt, render):
        self.prev_wait_time = self.total_wait_time
        self.prev_passed = self.cars_passed

        self.createCar()

        # Update cars
        for lane in self.lanes:
            ordered = sorted(lane, key=lambda c: c.distance, reverse=True)
            for idx, car in enumerate(ordered):
                lead = ordered[idx - 1] if idx > 0 else None
                light = self.horiz_light if car.lane in ["lr", "rl"] else self.vert_light
                car.update(dt, light, lead)

        # Remove cars that left the screen
        for lane in self.lanes:
            for i in range(len(lane)-1, -1, -1):
                if lane[i].distance > self.screen_height + self.car_length:
                    self.cars_passed += 1
                    lane.pop(i)

        # Check for crashes
        self.prev_crashes = self.num_crashes
        self.checkForCrashes()
        crash_diff = self.num_crashes - self.prev_crashes
        wait_diff = self.total_wait_time - self.prev_wait_time
        passed_diff = self.cars_passed - self.prev_passed

        if render:
            if not pygame.get_init():
                self.init_pygame()
            self.draw_screen()

        # Compute reward
        # reward = -waiting time difference - (10000 × number of new crashes)
        if self.reward_function == 'normal':
            waiting_rew = self.waiting_rew()
            passed_rew = self.passed_car_rew()
            reward = waiting_rew + passed_rew

        self.average_wait_time = (self.total_wait_time / self.num_cars) if self.num_cars > 0 else 0.0

        # Return reward and optional info
        info = {
            "vert_light": self.vert_light,
            "horiz_light": self.horiz_light,
            "total_wait_time": self.total_wait_time,
            "average_wait_time": self.average_wait_time,
            "wait_diff": wait_diff,
            "num_crashes": self.num_crashes,
            "new_crashes": crash_diff,
            "cars_passed": self.cars_passed,
            "cars_per_lane": [len(l) for l in self.lanes],
            "waiting_rew": waiting_rew,
            "passed_rew": passed_rew
        }
        self.total_time += dt


        return reward, info