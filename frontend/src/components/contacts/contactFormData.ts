// Los datos de un formulario de contacto, sin nada de interfaz.
//
// Vivían dentro de `ContactForm.tsx`, junto al componente. Un fichero que exporta a la vez un
// componente y funciones sueltas pierde la recarga en caliente durante el desarrollo, y además
// mezcla dos cosas distintas: cómo se pinta el formulario y qué campos tiene un contacto.
import type { Contact } from './types';

export interface ContactFormData {
  first_name: string;
  last_name: string;
  display_name: string;
  nickname: string;
  email: string;
  email2: string;
  email3: string;
  phone: string;
  phone_mobile: string;
  phone_work: string;
  phone_home: string;
  fax: string;
  company: string;
  organization: string;
  job_title: string;
  department: string;
  address_street: string;
  address_city: string;
  address_state: string;
  address_zip: string;
  address_country: string;
  birthday: string;
  website: string;
  im_address: string;
  notes: string;
}

export function emptyFormData(): ContactFormData {
  return {
    first_name: '', last_name: '', display_name: '', nickname: '',
    email: '', email2: '', email3: '',
    phone: '', phone_mobile: '', phone_work: '', phone_home: '', fax: '',
    company: '', organization: '', job_title: '', department: '',
    address_street: '', address_city: '', address_state: '', address_zip: '', address_country: '',
    birthday: '', website: '', im_address: '', notes: '',
  };
}

export function contactToFormData(c: Contact): ContactFormData {
  return {
    first_name: c.first_name || '', last_name: c.last_name || '',
    display_name: c.display_name || '', nickname: c.nickname || '',
    email: c.email || '', email2: c.email2 || '', email3: c.email3 || '',
    phone: c.phone || '', phone_mobile: c.phone_mobile || '',
    phone_work: c.phone_work || '', phone_home: c.phone_home || '', fax: c.fax || '',
    company: c.company || '', organization: c.organization || '',
    job_title: c.job_title || '', department: c.department || '',
    address_street: c.address_street || '', address_city: c.address_city || '',
    address_state: c.address_state || '', address_zip: c.address_zip || '',
    address_country: c.address_country || '',
    birthday: c.birthday || '', website: c.website || '',
    im_address: c.im_address || '', notes: c.notes || '',
  };
}
