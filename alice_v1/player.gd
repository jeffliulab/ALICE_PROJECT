extends CharacterBody2D

@export var speed = 100 # 移动速度，你可以在 Inspector 里调整

# 提前获取子节点的引用，方便使用
@onready var animation_player = $AnimationPlayer
@onready var sprite_2d = $Sprite2D

func _physics_process(delta):
	# 1. 获取键盘输入
	var direction = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")

	# 2. 根据方向和速度，设置角色的期望速度
	velocity = direction * speed

	# 3. Godot 的魔法函数：移动角色并处理碰撞
	move_and_slide()

	# 4. 根据移动状态更新动画
	update_animation()


func update_animation():
	if velocity.length() == 0:
		# 如果速度为0（没有移动），停止播放
		animation_player.stop()
	else:
		# 如果在移动
		var direction = "down" # 默认方向
		if velocity.y < 0:
			direction = "up"
		elif velocity.x < 0:
			direction = "left"
		elif velocity.x > 0:
			direction = "right"

		# 播放对应的动画
		if direction == "right":
			animation_player.play("walk_right")
		elif direction == "left":
			animation_player.play("walk_left")
		elif direction == "down":
			animation_player.play("walk_down")
		elif direction == "up":
			animation_player.play("walk_up")
		else:
			animation_player.play("walk_" + direction)
