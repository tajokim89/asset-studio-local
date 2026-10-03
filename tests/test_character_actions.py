"""Action builder is pure prompt authoring: no engine or cloud invocation."""
from pathlib import Path
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[1]

def run(script):
    result=subprocess.run([shutil.which('node'),'-e',script],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_character_action_combinations_and_timing_are_consistent():
    run(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const window={};vm.runInNewContext(fs.readFileSync('src/character-actions.js','utf8'),{window});const c=window.CharacterActions;
function verify(config){const r=c.build({duration:2,...config});const beats=[...r.prompt.matchAll(/\[([\d.]+)s-([\d.]+)s\]/g)];assert.equal(beats.length,4);assert.equal(+beats[0][1],0);assert.equal(+beats[3][2],2);for(let i=0;i<4;i++){assert.ok(+beats[i][2]>+beats[i][1]);if(i)assert.equal(beats[i][1],beats[i-1][2]);}return r;}
for(const action of ['idle','walk','run','jump']){const r=verify({group:'basic',action});assert.equal(r.loop,action!=='jump');if(action==='jump')assert.match(r.prompt,/actual upward and downward displacement/);}
for(const equipment of Object.keys(c.options.equipment))for(const attack of c.attackTypes(equipment))for(const path of c.pathsFor(attack))for(const strength of ['light','normal','heavy'])for(const feet of ['in-place','step'])for(const hand of ['right','left']){
const r=verify({group:'melee',equipment,attack,path,strength,feet,hand});assert.equal(r.loop,false);assert.equal(r.weights[1],.15);assert.doesNotMatch(r.prompt,/손를|손로|주먹를|다리을/);assert.ok(r.stages[1].includes({punch:'주먹을 뻗는다',kick:'발차기를 한다',slash:'벤다',thrust:'찌른다',smash:'내려친다'}[attack]));assert.match(r.prompt,/anatomical character-local/);if(equipment==='shield'){assert.match(r.prompt,/shield does NOT attack/);assert.match(r.stages[0],/몸통 약간 뒤/);assert.match(r.stages[1],/앞으로 뻗거나 공격하지/);assert.match(r.stages[3],/무기를 먼저 회수한 뒤에만/);}
}
assert.match(verify({group:'melee',equipment:'shield',offhand:'defend'}).prompt,/No simultaneous shield attack/);
assert.match(verify({group:'melee',equipment:'twohand'}).prompt,/same original weapon/);
assert.match(verify({group:'melee',equipment:'dual',hand:'left'}).prompt,/selected left hand attacks/);
assert.throws(()=>verify({group:'melee',equipment:'unarmed',attack:'slash'}));
assert.throws(()=>verify({group:'melee',attack:'thrust',path:'down'}));
assert.throws(()=>verify({group:'melee',attack:'shield_bash'}));
for(const weapon of ['bow','crossbow'])for(const phase of ['fire','prepare-fire','reload'])for(const bowSupport of ['left','right'])for(const grip of ['onehand','twohand'])for(const aim of ['level','up','down'])for(const projectile of ['separate','visible']){
const r=verify({group:'ranged',weapon,phase,bowSupport,grip,aim,projectile});assert.equal(r.loop,false);
assert.doesNotMatch(r.prompt,/no extra objects|never release|both hands.*throughout/i);assert.doesNotMatch(r.prompt,/손가\s|손는\s/);
if(phase==='reload'){assert.match(r.prompt,/Reload only: do not fire/);assert.doesNotMatch(r.prompt,/Fire one shot only|exactly one projectile leaving/);if(weapon==='crossbow')assert.match(r.prompt,/hands explicitly change positions/);}
else{assert.match(r.prompt,/Fire one shot only/);assert.match(r.prompt,/Do not reload/);if(projectile==='separate')assert.match(r.prompt,/Keep the loaded arrow or bolt visible until release/);else assert.match(r.prompt,/exactly one projectile/);if(weapon==='bow')assert.match(r.prompt,/string fingers may open/);}
}
assert.equal(verify({group:'shield',shieldAction:'guard'}).loop,true);assert.equal(verify({group:'shield',shieldAction:'bash'}).loop,false);
assert.match(verify({group:'shield',shieldAction:'bash'}).prompt,/weapon hand stays passive/);
for(const duration of [1,1.5,3.3,6])assert.ok(c.build({duration,group:'melee'}).prompt.includes(`s-${duration}s]`));
assert.throws(()=>c.build({duration:7}));
''')


def test_dialog_is_contextual_and_import_only_preserves_frame_and_source():
    run(r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes={};function node(id){return nodes[id] ||= {value:'',hidden:false,listeners:{},addEventListener(e,f){this.listeners[e]=f},replaceChildren(...children){this.children=children;this.value=children[0]?.value||''},showModal(){this.open=true},close(){this.open=false},focus(){this.focused=true},scrollIntoView(){},dispatchEvent(){this.inputs=(this.inputs||0)+1}}}
const values={caGroup:'basic',caBasicAction:'walk',caEquipment:'onehand',caAttack:'slash',caPath:'right-left',caStrength:'normal',caFeet:'in-place',caHand:'right',caOffhand:'retract',caWeapon:'bow',caPhase:'fire',caBowSupport:'left',caGrip:'twohand',caAim:'level',caProjectile:'separate',caShieldAction:'guard',spriteVideoDuration:'2',spriteVideoFrames:'25'};for(const[id,value]of Object.entries(values))node(id).value=value;
const sections=['basic','melee','ranged','shield'].map(group=>({dataset:{actionGroup:group},hidden:false}));let confirmation=true,confirms=0;const window={confirm(){confirms++;return confirmation}},document={getElementById:node,createElement:()=>({}),querySelectorAll:()=>sections},context={window,document,Event:function(){}};
vm.runInNewContext(fs.readFileSync('src/character-actions.js','utf8'),context);vm.runInNewContext(fs.readFileSync('src/character-action-ui.js','utf8'),context);
window.CharacterActionBuilder.open();assert.equal(sections.filter(s=>!s.hidden).length,1);assert.equal(sections[0].hidden,false);
node('caGroup').value='melee';node('caEquipment').value='shield';node('caEquipment').listeners.change();assert.equal(node('caOffhandField').hidden,false);assert.equal(node('caHandField').hidden,true);
node('caEquipment').value='dual';node('caEquipment').listeners.change();assert.equal(node('caOffhandField').hidden,true);assert.equal(node('caHandField').hidden,false);
node('caGroup').value='ranged';node('caWeapon').value='crossbow';node('caPhase').value='reload';node('caWeapon').listeners.change();assert.equal(node('caBowRole').hidden,true);assert.equal(node('caGripField').hidden,false);assert.equal(node('caProjectileField').hidden,true);
node('characterActionApply').listeners.click();assert.match(node('assetCorePrompt').value,/Reload only/);assert.equal(confirms,0);assert.equal(node('spriteVideoFrames').value,'25');assert.equal(node('characterActionDialog').open,false);
window.CharacterActionBuilder.open();node('caGroup').value='basic';node('caGroup').listeners.change();node('characterActionApply').listeners.click();assert.equal(confirms,0);
node('assetCorePrompt').value='my edited text';confirmation=false;node('characterActionApply').listeners.click();assert.equal(node('assetCorePrompt').value,'my edited text');assert.equal(confirms,1);
confirmation=true;node('characterActionApply').listeners.click();assert.notEqual(node('assetCorePrompt').value,'my edited text');assert.equal(node('assetCorePrompt').inputs,3);
node('characterDirectPrompt').listeners.click();assert.equal(node('assetCorePrompt').focused,true);
assert.equal(nodes.familyGenerateAi,undefined);assert.equal(nodes.imageReferencePin,undefined);
''')


def test_primary_entry_uses_dedicated_dialog_without_generation_side_effects():
    html=(ROOT/'index.html').read_text(encoding='utf-8')
    assert 'id="spriteWizardOpen" type="button">캐릭터 액션 만들기' in html
    assert 'id="characterDirectPrompt"' in html
    assert 'id="characterActionDialog"' in html
    assert 'id="spriteVideoFrames" class="input" type="number" min="2" max="64" value="25"' in html
    integration=(ROOT/'src/sprite-video.js').read_text(encoding='utf-8')
    entry=integration.split("byId('spriteWizardOpen').addEventListener",1)[1].split('\n',1)[0]
    assert 'CharacterActionBuilder.open()' in entry and 'spritePromptWizard' not in entry
    ui=(ROOT/'src/character-action-ui.js').read_text(encoding='utf-8')
    for forbidden in ['fetch(', 'generateAiAsset(', 'submitGenerationJob(', 'imageObjectToDataUrl(', 'imageReferencePin']:
        assert forbidden not in ui
