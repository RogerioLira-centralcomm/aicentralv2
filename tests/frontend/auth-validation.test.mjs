import test from 'node:test';
import assert from 'node:assert/strict';
import {firstInvalid, hasErrors, validateConfirmation, validateEmail, validateName, validateNewPassword} from '../../frontend/cadu-design-system/auth/validation.mjs';

test('email de cliente: formato completo', () => {
  assert.equal(validateEmail('nome@empresa.com'), '');
  assert.equal(validateEmail(' nome@empresa.com.br '), '');
  for (const bad of ['', 'nome', 'nome@', 'nome@empresa', 'a b@empresa.com']) assert.notEqual(validateEmail(bad), '', bad);
});

test('acesso corporativo: usuário ou email @centralcomm.media', () => {
  const corporate = value => validateEmail(value, {corporate: true});
  assert.equal(corporate('apolo.lira'), '');
  assert.equal(corporate('Apolo.Lira@centralcomm.media'), '');
  for (const bad of ['', 'apolo@gmail.com', '.apolo', 'apo lo', 'a@b@centralcomm.media']) assert.notEqual(corporate(bad), '', bad);
});

test('senha nova: mínimo de 8 e confirmação igual (mesma regra do servidor)', () => {
  assert.notEqual(validateNewPassword('1234567'), '');
  assert.equal(validateNewPassword('12345678'), '');
  assert.notEqual(validateConfirmation('12345678', ''), '');
  assert.notEqual(validateConfirmation('12345678', '12345679'), '');
  assert.equal(validateConfirmation('12345678', '12345678'), '');
  assert.notEqual(validateName('A'), '');
  assert.equal(validateName('Ana Lima'), '');
});

test('primeiro campo inválido segue a ordem do formulário', () => {
  const errors = {name: '', email: 'x', password: 'y'};
  assert.equal(firstInvalid(errors, ['name', 'email', 'password']), 'email');
  assert.equal(hasErrors(errors), true);
  assert.equal(hasErrors({a: '', b: ''}), false);
});
