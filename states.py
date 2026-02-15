from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    name = State()
    surname = State()
    age = State()
    gender = State()
    district = State()
    confirm = State()

class Work(StatesGroup):
    delivery_type = State()
    delivery_route = State()
    odd_job_wires = State()
    loader_sorting = State()
    cleaner_scrub = State()
    construction_mix = State()
    hacker_guess = State()
    bartender_mix = State()

class Business(StatesGroup):
    pass

class Casino(StatesGroup):
    slots_bet = State()
    blackjack_bet = State()
    blackjack_game = State()

class Bank(StatesGroup):
    transfer_amount = State()
    transfer_recipient = State()
    credit_amount = State()
    credit_term = State()
    credit_confirm = State()
    repay_amount = State()

class Transfer(StatesGroup):
    amount = State()
    recipient = State()
    item_id = State()
    confirm = State() # Вернули

class TaxiOrder(StatesGroup):
    destination = State()
    confirm = State()

class PersonalTravel(StatesGroup):
    destination = State()
    confirm = State()
