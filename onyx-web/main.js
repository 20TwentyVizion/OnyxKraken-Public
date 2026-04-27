const app = new PIXI.Application({
    width: window.innerWidth,
    height: window.innerHeight,
    backgroundColor: 0x1a1a1a,
    resizeTo: window
});
document.body.appendChild(app.view);

const factory = dragonBones.PixiFactory.factory;

app.loader
    .add("dragonbone_ske", "NewDragon_ske.json")
    .add("dragonbone_tex", "NewDragon_tex.json")
    .add("dragonbone_png", "NewDragon_tex.png")
    .load((loader, resources) => {
        factory.parseDragonBonesData(resources.dragonbone_ske.data);
        factory.parseTextureAtlasData(resources.dragonbone_tex.data, resources.dragonbone_png.texture);

        const armatureDisplay = factory.buildArmatureDisplay("NewDragon");

        armatureDisplay.animation.play("idle");

        armatureDisplay.x = window.innerWidth / 2;
        armatureDisplay.y = window.innerHeight / 2;
        app.stage.addChild(armatureDisplay);
    });