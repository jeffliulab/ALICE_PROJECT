/**
 * Phaser 3 Game Scene for Smallville visualization.
 *
 * Loads the Tiled JSON map with multiple tileset layers, renders characters
 * as colored circles with name labels (since we use procedural rendering
 * to avoid sprite atlas complexity), and handles camera controls.
 */
import Phaser from 'phaser';

export const TILE_SIZE = 32;

interface PersonaSprite {
  circle: Phaser.GameObjects.Arc;
  label: Phaser.GameObjects.Text;
  emoji: Phaser.GameObjects.Text;
  targetX: number;
  targetY: number;
}

// Assign consistent colors to personas
const COLORS = [
  0xe94560, 0x4ecca3, 0xf5a623, 0x7b68ee, 0xff6b6b,
  0x48dbfb, 0xff9ff3, 0x00d2d3, 0xfeca57, 0x54a0ff,
  0x5f27cd, 0x01a3a4, 0xf368e0, 0xff6348, 0x2ed573,
  0x1e90ff, 0xffa502, 0x7bed9f, 0x70a1ff, 0xeccc68,
  0xa29bfe, 0xfd79a8, 0x6c5ce7, 0x00cec9, 0xfdcb6e,
];

export class GameScene extends Phaser.Scene {
  private personas: Map<string, PersonaSprite> = new Map();
  private mapLoaded = false;

  constructor() {
    super({ key: 'GameScene' });
  }

  preload() {
    // Load the Tiled map and all referenced tilesets
    this.load.tilemapTiledJSON('map', '/assets/maps/the_ville_jan7.json');

    // Load tileset images matching the Tiled JSON references
    this.load.image('CuteRPG_Field_B', '/assets/tilesets/cute_rpg/CuteRPG_Field_B.png');
    this.load.image('CuteRPG_Field_C', '/assets/tilesets/cute_rpg/CuteRPG_Field_C.png');
    this.load.image('CuteRPG_Harbor_C', '/assets/tilesets/cute_rpg/CuteRPG_Harbor_C.png');
    this.load.image('Room_Builder_32x32', '/assets/tilesets/v1/Room_Builder_32x32.png');
    this.load.image('CuteRPG_Village_B', '/assets/tilesets/cute_rpg/CuteRPG_Village_B.png');
    this.load.image('CuteRPG_Forest_B', '/assets/tilesets/cute_rpg/CuteRPG_Forest_B.png');
    this.load.image('CuteRPG_Desert_C', '/assets/tilesets/cute_rpg/CuteRPG_Desert_C.png');
    this.load.image('CuteRPG_Mountains_B', '/assets/tilesets/cute_rpg/CuteRPG_Mountains_B.png');
    this.load.image('CuteRPG_Desert_B', '/assets/tilesets/cute_rpg/CuteRPG_Desert_B.png');
    this.load.image('CuteRPG_Forest_C', '/assets/tilesets/cute_rpg/CuteRPG_Forest_C.png');
    this.load.image('interiors_pt1', '/assets/tilesets/v1/interiors_pt1.png');
    this.load.image('interiors_pt2', '/assets/tilesets/v1/interiors_pt2.png');
    this.load.image('interiors_pt3', '/assets/tilesets/v1/interiors_pt3.png');
    this.load.image('interiors_pt4', '/assets/tilesets/v1/interiors_pt4.png');
    this.load.image('interiors_pt5', '/assets/tilesets/v1/interiors_pt5.png');
    this.load.image('blocks', '/assets/tilesets/blocks/blocks_1.png');
    this.load.image('blocks_2', '/assets/tilesets/blocks/blocks_2.png');
    this.load.image('blocks_3', '/assets/tilesets/blocks/blocks_3.png');
  }

  create() {
    const map = this.make.tilemap({ key: 'map' });

    // Add all tilesets
    const tilesetNames = [
      'CuteRPG_Field_B', 'CuteRPG_Field_C', 'CuteRPG_Harbor_C',
      'Room_Builder_32x32', 'CuteRPG_Village_B', 'CuteRPG_Forest_B',
      'CuteRPG_Desert_C', 'CuteRPG_Mountains_B', 'CuteRPG_Desert_B',
      'CuteRPG_Forest_C', 'interiors_pt1', 'interiors_pt2',
      'interiors_pt3', 'interiors_pt4', 'interiors_pt5',
      'blocks', 'blocks_2', 'blocks_3',
    ];
    const tilesets = tilesetNames.map(name => map.addTilesetImage(name, name)!).filter(Boolean);

    // Render visible layers (skip metadata layers like Collisions, Blocks, etc)
    const visibleLayers = [
      'Bottom Ground', 'Exterior Ground', 'Exterior Decoration L1',
      'Exterior Decoration L2', 'Interior Ground', 'Wall',
      'Interior Furniture L1', 'Interior Furniture L2 ',
      'Foreground L1', 'Foreground L2',
    ];

    for (const layerName of visibleLayers) {
      const layer = map.createLayer(layerName, tilesets);
      if (layer) {
        layer.setDepth(visibleLayers.indexOf(layerName));
      }
    }

    // Camera setup
    this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    this.cameras.main.setZoom(1);

    // Mouse wheel zoom
    this.input.on('wheel', (_p: any, _gos: any, _dx: number, dy: number) => {
      const cam = this.cameras.main;
      const newZoom = Phaser.Math.Clamp(cam.zoom - dy * 0.001, 0.3, 3);
      cam.setZoom(newZoom);
    });

    // Drag to pan
    let dragStartX = 0, dragStartY = 0;
    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => {
      dragStartX = p.x; dragStartY = p.y;
    });
    this.input.on('pointermove', (p: Phaser.Input.Pointer) => {
      if (!p.isDown) return;
      const cam = this.cameras.main;
      cam.scrollX -= (p.x - dragStartX) / cam.zoom;
      cam.scrollY -= (p.y - dragStartY) / cam.zoom;
      dragStartX = p.x; dragStartY = p.y;
    });

    // Center on approximate town center
    this.cameras.main.centerOn(70 * TILE_SIZE, 50 * TILE_SIZE);

    this.mapLoaded = true;
  }

  update() {
    // Smooth movement interpolation
    for (const [, ps] of this.personas) {
      const dx = ps.targetX - ps.circle.x;
      const dy = ps.targetY - ps.circle.y;
      if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
        ps.circle.x += dx * 0.2;
        ps.circle.y += dy * 0.2;
      } else {
        ps.circle.x = ps.targetX;
        ps.circle.y = ps.targetY;
      }
      ps.label.setPosition(ps.circle.x, ps.circle.y - 20);
      ps.emoji.setPosition(ps.circle.x, ps.circle.y + 16);
    }
  }

  addPersona(name: string, tileX: number, tileY: number, emoji: string) {
    if (!this.mapLoaded) {
      // Retry after scene is ready
      this.time?.delayedCall(500, () => this.addPersona(name, tileX, tileY, emoji));
      return;
    }
    if (this.personas.has(name)) return;

    const px = tileX * TILE_SIZE + TILE_SIZE / 2;
    const py = tileY * TILE_SIZE + TILE_SIZE / 2;
    const idx = this.personas.size % COLORS.length;

    const circle = this.add.circle(px, py, 10, COLORS[idx], 0.9)
      .setDepth(100).setStrokeStyle(2, 0xffffff);

    const label = this.add.text(px, py - 20, name.split(' ')[0], {
      fontSize: '10px', color: '#ffffff', backgroundColor: '#000000aa',
      padding: { x: 2, y: 1 },
    }).setOrigin(0.5).setDepth(101);

    const emojiText = this.add.text(px, py + 16, emoji || '🙂', {
      fontSize: '12px',
    }).setOrigin(0.5).setDepth(101);

    this.personas.set(name, { circle, label, emoji: emojiText, targetX: px, targetY: py });
  }

  movePersona(name: string, tileX: number, tileY: number, emoji?: string) {
    const ps = this.personas.get(name);
    if (!ps) {
      this.addPersona(name, tileX, tileY, emoji || '🙂');
      return;
    }
    ps.targetX = tileX * TILE_SIZE + TILE_SIZE / 2;
    ps.targetY = tileY * TILE_SIZE + TILE_SIZE / 2;
    if (emoji) ps.emoji.setText(emoji);
  }

  centerOn(tileX: number, tileY: number) {
    this.cameras.main.centerOn(tileX * TILE_SIZE, tileY * TILE_SIZE);
  }
}
